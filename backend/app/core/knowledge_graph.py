"""Knowledge graph for claims, entities, and relationships."""
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
import networkx as nx
import structlog
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.db.models import Claim, ClaimRelation, Source

logger = structlog.get_logger()


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    id: str
    type: str  # "claim", "entity", "source"
    label: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the knowledge graph."""
    source: str
    target: str
    relation: str  # "SUPPORTS", "CONTRADICTS", "ABOUT", "FROM"
    confidence: float = 0.5
    data: Dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph:
    """Knowledge graph for research claims and relationships."""
    
    def __init__(self, embedding_model: str = 'all-MiniLM-L6-v2'):
        self.G = nx.DiGraph()
        self.embedding_model = SentenceTransformer(embedding_model)
        self.claim_embeddings: Dict[str, np.ndarray] = {}
        self.similarity_threshold = 0.75  # For finding related claims
    
    def add_claim(self, claim: Claim, source: Optional[Source] = None) -> str:
        """
        Add a claim to the graph.
        
        Args:
            claim: The claim to add
            source: Optional source for the claim
            
        Returns:
            Node ID
        """
        node_id = f"claim:{claim.id}"
        
        # Add claim node
        self.G.add_node(
            node_id,
            type="claim",
            label=claim.text[:100] + "..." if len(claim.text) > 100 else claim.text,
            data={
                "claim_id": claim.id,
                "text": claim.text,
                "confidence": claim.confidence,
                "verified": claim.verified,
                "verification_confidence": claim.verification_confidence,
                "evidence_level": claim.evidence_level,
            }
        )
        
        # Store embedding
        if claim.embedding:
            self.claim_embeddings[claim.id] = np.array(claim.embedding)
        else:
            # Generate embedding if not provided
            embedding = self.embedding_model.encode([claim.text])[0]
            self.claim_embeddings[claim.id] = embedding
        
        # Add entity nodes and edges
        for entity in claim.entities:
            entity_id = f"entity:{entity.lower().replace(' ', '_')}"
            
            if entity_id not in self.G:
                self.G.add_node(
                    entity_id,
                    type="entity",
                    label=entity,
                    data={"name": entity, "mentions": 1}
                )
            else:
                # Increment mention count
                self.G.nodes[entity_id]["data"]["mentions"] += 1
            
            # Add edge from claim to entity
            self.G.add_edge(
                node_id, entity_id,
                relation="ABOUT",
                confidence=claim.confidence
            )
        
        # Add source node and edge
        if source:
            source_id = f"source:{source.id}"
            
            if source_id not in self.G:
                self.G.add_node(
                    source_id,
                    type="source",
                    label=source.title or source.domain or "Unknown Source",
                    data={
                        "source_id": source.id,
                        "url": source.url,
                        "domain": source.domain,
                        "credibility_score": source.credibility_score,
                    }
                )
            
            # Add edge from claim to source
            self.G.add_edge(
                node_id, source_id,
                relation="FROM",
                confidence=1.0
            )
        
        # Find and link related claims
        self._link_related_claims(claim)
        
        return node_id
    
    def _link_related_claims(self, new_claim: Claim):
        """Find and create edges to related existing claims."""
        if new_claim.id not in self.claim_embeddings:
            return
        
        new_embedding = self.claim_embeddings[new_claim.id].reshape(1, -1)
        new_node_id = f"claim:{new_claim.id}"
        
        for existing_id, existing_embedding in self.claim_embeddings.items():
            if existing_id == new_claim.id:
                continue
            
            # Calculate similarity
            similarity = cosine_similarity(
                new_embedding,
                existing_embedding.reshape(1, -1)
            )[0, 0]
            
            if similarity > self.similarity_threshold:
                existing_node_id = f"claim:{existing_id}"
                
                # Determine relationship type
                relation = self._determine_relation(new_claim, existing_id)
                
                # Add edge
                self.G.add_edge(
                    new_node_id, existing_node_id,
                    relation=relation,
                    confidence=float(similarity),
                    data={"similarity": float(similarity)}
                )
                
                logger.debug(
                    f"Linked claims with {relation}",
                    similarity=similarity,
                    claim1=new_claim.id[:8],
                    claim2=existing_id[:8]
                )
    
    def _determine_relation(self, claim1: Claim, claim2_id: str) -> str:
        """Determine the relationship between two claims."""
        # This is a simplified version - could use LLM for more nuanced analysis
        
        # Check for contradiction indicators in text
        contradiction_indicators = [
            'however', 'but', 'contrary', 'opposite', 'disagree',
            'conflict', 'dispute', 'challenge', 'refute', 'debunk'
        ]
        
        text_lower = claim1.text.lower()
        has_contradiction = any(ind in text_lower for ind in contradiction_indicators)
        
        if has_contradiction:
            return "CONTRADICTS"
        
        # Check for supporting language
        support_indicators = [
            'support', 'confirm', 'agree', 'consistent', 'similar',
            'likewise', 'also', 'additionally', 'furthermore'
        ]
        
        has_support = any(ind in text_lower for ind in support_indicators)
        
        if has_support:
            return "SUPPORTS"
        
        return "RELATED_TO"
    
    def add_claim_relation(self, relation: ClaimRelation):
        """Add a claim relation to the graph."""
        source_node = f"claim:{relation.source_claim_id}"
        target_node = f"claim:{relation.target_claim_id}"
        
        if source_node in self.G and target_node in self.G:
            self.G.add_edge(
                source_node, target_node,
                relation=relation.relation_type,
                confidence=relation.confidence,
                data={"explanation": relation.explanation}
            )
    
    def find_contradictions(self) -> List[Tuple[str, str, float]]:
        """
        Find all contradictory claim pairs.
        
        Returns:
            List of (claim1_id, claim2_id, confidence) tuples
        """
        contradictions = []
        
        for u, v, data in self.G.edges(data=True):
            if data.get('relation') == 'CONTRADICTS':
                # Extract claim IDs from node IDs
                claim1_id = u.replace('claim:', '')
                claim2_id = v.replace('claim:', '')
                confidence = data.get('confidence', 0.5)
                
                contradictions.append((claim1_id, claim2_id, confidence))
        
        return contradictions
    
    def find_claim_clusters(self) -> List[List[str]]:
        """
        Find clusters of related claims using community detection.
        
        Returns:
            List of claim ID clusters
        """
        # Get subgraph of only claim nodes
        claim_nodes = [n for n, d in self.G.nodes(data=True) if d.get('type') == 'claim']
        claim_subgraph = self.G.subgraph(claim_nodes)
        
        if len(claim_nodes) < 3:
            return [[n.replace('claim:', '') for n in claim_nodes]]
        
        try:
            # Use Louvain community detection
            from networkx.algorithms.community import louvain_communities
            communities = louvain_communities(claim_subgraph)
            
            # Convert to claim IDs
            clusters = [
                [n.replace('claim:', '') for n in community]
                for community in communities
            ]
            
            return clusters
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")
            # Fallback: return all claims as one cluster
            return [[n.replace('claim:', '') for n in claim_nodes]]
    
    def get_claim_context(self, claim_id: str) -> Dict[str, Any]:
        """
        Get the context around a claim (related claims, entities, sources).
        
        Args:
            claim_id: The claim ID
            
        Returns:
            Context dictionary
        """
        node_id = f"claim:{claim_id}"
        
        if node_id not in self.G:
            return {}
        
        # Get neighbors
        neighbors = list(self.G.neighbors(node_id))
        predecessors = list(self.G.predecessors(node_id))
        
        context = {
            "claim": self.G.nodes[node_id]["data"],
            "supports": [],
            "contradicts": [],
            "related": [],
            "entities": [],
            "sources": []
        }
        
        for neighbor in neighbors + predecessors:
            node_data = self.G.nodes[neighbor]
            edge_data = self.G.get_edge_data(node_id, neighbor) or {}
            edge_data_reverse = self.G.get_edge_data(neighbor, node_id) or {}
            
            relation = edge_data.get('relation') or edge_data_reverse.get('relation')
            
            if node_data.get('type') == 'entity':
                context["entities"].append(node_data["data"])
            elif node_data.get('type') == 'source':
                context["sources"].append(node_data["data"])
            elif node_data.get('type') == 'claim':
                claim_data = {
                    "claim_id": node_data["data"]["claim_id"],
                    "text": node_data["data"]["text"],
                    "confidence": node_data["data"]["confidence"]
                }
                
                if relation == "SUPPORTS":
                    context["supports"].append(claim_data)
                elif relation == "CONTRADICTS":
                    context["contradicts"].append(claim_data)
                else:
                    context["related"].append(claim_data)
        
        return context
    
    def to_vis_data(self) -> Dict[str, List[Dict]]:
        """
        Convert graph to visualization format for D3.js.
        
        Returns:
            Dict with "nodes" and "edges" lists
        """
        nodes = []
        edges = []
        
        # Color mapping
        type_colors = {
            "claim": "#3b82f6",     # Blue
            "entity": "#10b981",    # Green
            "source": "#6b7280",    # Gray
        }
        
        relation_colors = {
            "SUPPORTS": "#10b981",    # Green
            "CONTRADICTS": "#ef4444",  # Red
            "ABOUT": "#9ca3af",        # Gray
            "FROM": "#6b7280",         # Dark gray
            "RELATED_TO": "#d1d5db",   # Light gray
        }
        
        for node_id, data in self.G.nodes(data=True):
            node_type = data.get('type', 'unknown')
            node_data = data.get('data', {})
            
            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": data.get('label', node_id),
                "color": type_colors.get(node_type, "#9ca3af"),
                "data": node_data,
                # Size based on importance
                "size": 10 + (node_data.get('mentions', 0) * 2) if node_type == 'entity' else 15,
            })
        
        for source, target, data in self.G.edges(data=True):
            relation = data.get('relation', 'RELATED_TO')
            
            edges.append({
                "source": source,
                "target": target,
                "relation": relation,
                "color": relation_colors.get(relation, "#d1d5db"),
                "confidence": data.get('confidence', 0.5),
                # Thickness based on confidence
                "width": 1 + data.get('confidence', 0.5) * 3,
            })
        
        return {"nodes": nodes, "edges": edges}
    
    def to_graphml(self) -> str:
        """Export graph to GraphML format."""
        import io
        buffer = io.BytesIO()
        nx.write_graphml(self.G, buffer)
        return buffer.getvalue().decode('utf-8')
    
    def get_statistics(self) -> Dict[str, int]:
        """Get graph statistics."""
        node_types = {}
        for _, data in self.G.nodes(data=True):
            node_type = data.get('type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        edge_types = {}
        for _, _, data in self.G.edges(data=True):
            edge_type = data.get('relation', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "claim_nodes": node_types.get('claim', 0),
            "entity_nodes": node_types.get('entity', 0),
            "source_nodes": node_types.get('source', 0),
            "supports_edges": edge_types.get('SUPPORTS', 0),
            "contradicts_edges": edge_types.get('CONTRADICTS', 0),
            "connected_components": nx.number_weakly_connected_components(self.G),
        }
