"""Claim verification engine using multiple methods."""
from typing import List, Tuple, Optional
from enum import Enum
import structlog
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

from app.db.models import Claim, Source, VerificationMethod

logger = structlog.get_logger()


class VerificationEngine:
    """
    Verify claims against source text using multiple methods:
    1. Exact match (fast)
    2. Semantic similarity (embedding-based)
    3. NLI (Natural Language Inference) - most accurate
    """
    
    def __init__(self, embedding_model: str = 'all-MiniLM-L6-v2'):
        self.embedding_model = SentenceTransformer(embedding_model)
        self.semantic_threshold = 0.75
        self.nli_model = None  # Lazy-loaded
    
    def verify_claim(
        self, 
        claim: Claim, 
        source: Source,
        use_nli: bool = True
    ) -> Tuple[bool, VerificationMethod, float, Optional[str]]:
        """
        Verify a claim against its source.
        
        Args:
            claim: The claim to verify
            source: The source to verify against
            use_nli: Whether to use NLI (slower but more accurate)
            
        Returns:
            Tuple of (verified, method, confidence, excerpt)
        """
        if not source.text:
            return False, VerificationMethod.NONE, 0.0, None
        
        # Layer 1: Exact match (fastest)
        exact_result = self._verify_exact(claim.text, source.text)
        if exact_result[0]:
            return (
                True, 
                VerificationMethod.EXACT, 
                exact_result[1],
                exact_result[2]
            )
        
        # Layer 2: Semantic similarity
        semantic_result = self._verify_semantic(claim.text, source.text)
        if semantic_result[0] and semantic_result[1] > 0.85:
            return (
                True,
                VerificationMethod.SEMANTIC,
                semantic_result[1],
                semantic_result[2]
            )
        
        # Layer 3: NLI (most accurate, slowest)
        if use_nli and semantic_result[1] > 0.65:
            nli_result = self._verify_nli(claim.text, source.text)
            if nli_result[0]:
                return (
                    True,
                    VerificationMethod.NLI,
                    nli_result[1],
                    nli_result[2]
                )
        
        # Not verified - return best attempt
        if semantic_result[1] > 0.5:
            return (
                False,
                VerificationMethod.SEMANTIC,
                semantic_result[1],
                semantic_result[2]
            )
        
        return False, VerificationMethod.NONE, 0.0, None
    
    def _verify_exact(
        self, 
        claim: str, 
        source_text: str
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Check for exact or near-exact matches.
        
        Returns: (verified, confidence, excerpt)
        """
        claim_lower = claim.lower().strip()
        source_lower = source_text.lower()
        
        # Direct containment
        if claim_lower in source_lower:
            # Find the position and extract context
            idx = source_lower.find(claim_lower)
            excerpt = self._extract_excerpt(source_text, idx, len(claim))
            return True, 0.95, excerpt
        
        # Check for key phrases (remove stop words)
        claim_words = self._extract_key_words(claim)
        if len(claim_words) >= 3:
            # Check if all key words appear in close proximity
            if self._check_proximity(claim_words, source_text):
                excerpt = self._find_best_excerpt(claim_words, source_text)
                return True, 0.85, excerpt
        
        return False, 0.0, None
    
    def _verify_semantic(
        self, 
        claim: str, 
        source_text: str
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Verify using semantic similarity (embeddings).
        
        Returns: (verified, confidence, excerpt)
        """
        # Split source into chunks
        chunks = self._chunk_text(source_text, chunk_size=500, overlap=100)
        
        if not chunks:
            return False, 0.0, None
        
        # Get embeddings
        claim_embedding = self.embedding_model.encode([claim])
        chunk_embeddings = self.embedding_model.encode(chunks)
        
        # Calculate similarities
        similarities = cosine_similarity(claim_embedding, chunk_embeddings)[0]
        
        # Find best match
        best_idx = np.argmax(similarities)
        best_similarity = similarities[best_idx]
        best_chunk = chunks[best_idx]
        
        verified = best_similarity > self.semantic_threshold
        
        return verified, float(best_similarity), best_chunk
    
    def _verify_nli(
        self, 
        claim: str, 
        source_text: str
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Verify using Natural Language Inference.
        
        Returns: (verified, confidence, excerpt)
        """
        # Lazy-load NLI model
        if self.nli_model is None:
            try:
                from transformers import pipeline
                self.nli_model = pipeline(
                    "text-classification",
                    model="facebook/bart-large-mnli",
                    device=-1  # CPU
                )
            except Exception as e:
                logger.warning(f"NLI model load failed: {e}")
                return False, 0.0, None
        
        # Get top semantic matches first
        chunks = self._chunk_text(source_text, chunk_size=400, overlap=50)
        
        if not chunks:
            return False, 0.0, None
        
        # Quick semantic filter to find promising chunks
        claim_emb = self.embedding_model.encode([claim])
        chunk_embs = self.embedding_model.encode(chunks)
        similarities = cosine_similarity(claim_emb, chunk_embs)[0]
        
        # Only check top 3 chunks with NLI (expensive)
        top_indices = np.argsort(similarities)[-3:]
        
        best_confidence = 0.0
        best_excerpt = None
        
        for idx in top_indices:
            chunk = chunks[idx]
            
            try:
                # NLI: premise=chunk, hypothesis=claim
                result = self.nli_model(
                    f"{chunk} </s></s> {claim}",
                    candidate_labels=["entailment", "contradiction", "neutral"]
                )
                
                # Check if entailment is highest
                if result['labels'][0] == 'entailment':
                    confidence = result['scores'][0]
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_excerpt = chunk
                
            except Exception as e:
                logger.debug(f"NLI inference error: {e}")
                continue
        
        verified = best_confidence > 0.7
        return verified, best_confidence, best_excerpt
    
    def _extract_key_words(self, text: str) -> List[str]:
        """Extract key words (remove stop words)."""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
        }
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [w for w in words if w not in stop_words]
    
    def _check_proximity(
        self, 
        words: List[str], 
        text: str, 
        window: int = 100
    ) -> bool:
        """Check if words appear in close proximity in text."""
        text_lower = text.lower()
        word_positions = []
        
        for word in words:
            idx = text_lower.find(word)
            if idx != -1:
                word_positions.append(idx)
        
        if len(word_positions) < len(words) * 0.7:  # 70% of words must be found
            return False
        
        # Check if words are within window
        word_positions.sort()
        for i in range(len(word_positions) - len(words) + 1):
            if word_positions[i + len(words) - 1] - word_positions[i] <= window * len(words):
                return True
        
        return False
    
    def _find_best_excerpt(
        self, 
        words: List[str], 
        text: str, 
        context: int = 200
    ) -> str:
        """Find the best excerpt containing the key words."""
        text_lower = text.lower()
        
        # Find position with most word matches
        best_pos = 0
        best_count = 0
        
        for i in range(0, len(text) - 100, 50):
            window = text_lower[i:i+200]
            count = sum(1 for word in words if word in window)
            if count > best_count:
                best_count = count
                best_pos = i
        
        # Extract with context
        start = max(0, best_pos - context)
        end = min(len(text), best_pos + context * 2)
        
        excerpt = text[start:end]
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."
        
        return excerpt
    
    def _extract_excerpt(
        self, 
        text: str, 
        position: int, 
        length: int, 
        context: int = 200
    ) -> str:
        """Extract excerpt around a position."""
        start = max(0, position - context)
        end = min(len(text), position + length + context)
        
        excerpt = text[start:end]
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."
        
        return excerpt
    
    def _chunk_text(
        self, 
        text: str, 
        chunk_size: int = 500, 
        overlap: int = 100
    ) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                for delim in ['. ', '! ', '? ', '\n\n']:
                    last_delim = chunk.rfind(delim)
                    if last_delim > chunk_size * 0.5:
                        chunk = chunk[:last_delim + len(delim)]
                        end = start + len(chunk)
                        break
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return chunks
    
    async def verify_claims_batch(
        self, 
        claims: List[Claim], 
        sources: dict[str, Source]
    ) -> List[Claim]:
        """
        Verify multiple claims in batch.
        
        Args:
            claims: List of claims to verify
            sources: Dict mapping source_id to Source
            
        Returns:
            List of verified claims (with updated verification fields)
        """
        verified_claims = []
        
        for claim in claims:
            source = sources.get(claim.source_id)
            if not source:
                claim.verified = False
                claim.verification_confidence = 0.0
                verified_claims.append(claim)
                continue
            
            verified, method, confidence, excerpt = self.verify_claim(claim, source)
            
            claim.verified = verified
            claim.verification_method = method
            claim.verification_confidence = confidence
            claim.source_excerpt = excerpt
            
            verified_claims.append(claim)
        
        return verified_claims


# Singleton instance
verifier = VerificationEngine()
