"""Source curation: deduplication, credibility scoring, and filtering."""
import re
from typing import List, Dict, Set, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass
import structlog
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.core.crawler import CrawledContent
from app.db.models import Source, SourceType

logger = structlog.get_logger()


@dataclass
class CurationResult:
    """Result of source curation."""
    sources: List[Source]
    duplicates_removed: int
    low_quality_removed: int
    irrelevant_removed: int


class SourceCurator:
    """Curate sources: deduplicate, score credibility, filter."""
    
    # High-credibility domains
    TRUSTED_DOMAINS = {
        # Academic
        '.edu', '.ac.uk', '.ac.jp', '.ac.au',
        # Government
        '.gov', '.gov.uk', '.gov.au', '.gc.ca',
        # Encyclopedia
        'wikipedia.org', 'wikidata.org',
        # Major news
        'reuters.com', 'apnews.com', 'bloomberg.com', 'wsj.com',
        'nytimes.com', 'washingtonpost.com', 'theguardian.com',
        'bbc.com', 'bbc.co.uk', 'npr.org', 'economist.com',
        # Science
        'nature.com', 'science.org', 'cell.com', 'thelancet.com',
        'nejm.org', 'jamanetwork.com', 'pubmed.ncbi.nlm.nih.gov',
        # Tech
        'arxiv.org', 'github.com', 'stackoverflow.com',
    }
    
    # Low-credibility indicators
    LOW_QUALITY_INDICATORS = {
        'blogspot.', 'wordpress.com', 'medium.com',  # Personal blogs (unless verified)
        'forum', 'reddit.com/r/', 'quora.com',
    }
    
    def __init__(self, embedding_model: str = 'all-MiniLM-L6-v2'):
        self.embedding_model = SentenceTransformer(embedding_model)
        self.similarity_threshold = 0.85  # For semantic deduplication
    
    def curate(
        self,
        crawled: List[CrawledContent],
        query: str,
        min_credibility: float = 0.3,
        min_relevance: float = 0.5,
        max_sources: int = 50
    ) -> CurationResult:
        """
        Curate crawled content into high-quality sources.
        
        Args:
            crawled: List of crawled content
            query: Original research query
            min_credibility: Minimum credibility score (0-1)
            min_relevance: Minimum relevance score (0-1)
            max_sources: Maximum sources to return
            
        Returns:
            Curation result with curated sources
        """
        logger.info(f"Starting curation of {len(crawled)} sources")
        
        # Step 1: Convert to Source objects and calculate initial scores
        sources = [self._convert_to_source(c) for c in crawled if c.success]
        logger.info(f"Converted {len(sources)} successful crawls")
        
        # Step 2: Exact deduplication by content hash
        sources, dupes_exact = self._deduplicate_exact(sources)
        logger.info(f"Exact deduplication: removed {dupes_exact}, {len(sources)} remaining")
        
        # Step 3: Semantic deduplication
        sources, dupes_semantic = self._deduplicate_semantic(sources)
        logger.info(f"Semantic deduplication: removed {dupes_semantic}, {len(sources)} remaining")
        
        # Step 4: Calculate credibility scores
        sources = [self._calculate_credibility(s) for s in sources]
        
        # Step 5: Calculate relevance to query
        sources = self._calculate_relevance(sources, query)
        
        # Step 6: Filter by thresholds
        filtered = [
            s for s in sources
            if s.credibility_score >= min_credibility
            and s.credibility_factors.get('relevance', 0) >= min_relevance
        ]
        low_quality = len(sources) - len(filtered)
        logger.info(f"Filtered by thresholds: removed {low_quality}, {len(filtered)} remaining")
        
        # Step 7: Sort by combined score and limit
        filtered.sort(
            key=lambda s: (s.credibility_score * 0.6 + s.credibility_factors.get('relevance', 0) * 0.4),
            reverse=True
        )
        
        final = filtered[:max_sources]
        logger.info(f"Final curation: {len(final)} sources")
        
        return CurationResult(
            sources=final,
            duplicates_removed=dupes_exact + dupes_semantic,
            low_quality_removed=low_quality,
            irrelevant_removed=0  # Combined with low_quality
        )
    
    def _convert_to_source(self, crawled: CrawledContent) -> Source:
        """Convert crawled content to Source model."""
        # Detect source type
        source_type = self._detect_source_type(crawled.url, crawled.text)
        
        # Detect citations and methodology
        has_citations = self._detect_citations(crawled.text)
        has_methodology = self._detect_methodology(crawled.text)
        
        return Source(
            url=crawled.url,
            title=crawled.title,
            text=crawled.text,
            html=crawled.html,
            content_hash=crawled.content_hash,
            source_type=source_type,
            domain=self._get_domain(crawled.url),
            word_count=crawled.word_count,
            has_citations=has_citations,
            has_methodology=has_methodology,
        )
    
    def _detect_source_type(self, url: str, text: str) -> SourceType:
        """Detect the type of source."""
        domain = self._get_domain(url).lower()
        
        # Academic
        if any(d in domain for d in ['.edu', 'arxiv.org', 'pubmed', 'doi.org', 'scholar']):
            return SourceType.ACADEMIC
        
        # News
        news_domains = ['news', 'reuters', 'bloomberg', 'nytimes', 'bbc', 'cnn', 'guardian']
        if any(nd in domain for nd in news_domains):
            return SourceType.NEWS
        
        # Blog
        if any(bd in domain for bd in ['blog', 'medium.com', 'substack']):
            return SourceType.BLOG
        
        return SourceType.WEBPAGE
    
    def _detect_citations(self, text: str) -> bool:
        """Detect if text has academic citations."""
        citation_patterns = [
            r'\(\d{4}\)',  # (2023)
            r'\[\d+\]',  # [1]
            r'et al\.',
            r'doi:\s*10\.\d+',
            r'https?://doi\.org/',
            r'references?:',
            r'bibliography:',
        ]
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in citation_patterns)
    
    def _detect_methodology(self, text: str) -> bool:
        """Detect if text describes methodology."""
        method_terms = [
            'methodology', 'methods', 'study design', 'participants',
            'sample size', 'inclusion criteria', 'exclusion criteria',
            'randomized controlled trial', 'rct', 'cohort study',
            'statistical analysis', 'p-value', 'confidence interval'
        ]
        
        text_lower = text.lower()
        return any(term in text_lower for term in method_terms)
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def _deduplicate_exact(self, sources: List[Source]) -> Tuple[List[Source], int]:
        """Remove exact duplicates by content hash."""
        seen_hashes: Set[str] = set()
        unique: List[Source] = []
        
        for source in sources:
            if source.content_hash not in seen_hashes:
                seen_hashes.add(source.content_hash)
                unique.append(source)
        
        return unique, len(sources) - len(unique)
    
    def _deduplicate_semantic(self, sources: List[Source]) -> Tuple[List[Source], int]:
        """Remove near-duplicates using semantic similarity."""
        if len(sources) <= 1:
            return sources, 0
        
        # Get embeddings for titles + first 500 chars of text
        texts = [
            f"{s.title or ''} {s.text[:500] if s.text else ''}"
            for s in sources
        ]
        
        embeddings = self.embedding_model.encode(texts)
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(embeddings)
        
        # Find duplicates (excluding diagonal)
        to_remove: Set[int] = set()
        
        for i in range(len(sources)):
            if i in to_remove:
                continue
            
            for j in range(i + 1, len(sources)):
                if j in to_remove:
                    continue
                
                if similarity_matrix[i, j] > self.similarity_threshold:
                    # Keep the one with higher credibility
                    if sources[i].credibility_score >= sources[j].credibility_score:
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
                        break
        
        filtered = [s for i, s in enumerate(sources) if i not in to_remove]
        return filtered, len(to_remove)
    
    def _calculate_credibility(self, source: Source) -> Source:
        """Calculate credibility score for a source."""
        factors: Dict[str, float] = {}
        
        # Domain authority (0-0.4)
        domain_score = self._score_domain(source.domain)
        factors['domain_authority'] = domain_score
        
        # Content signals (0-0.3)
        content_score = 0.0
        if source.has_citations:
            content_score += 0.15
        if source.has_methodology:
            content_score += 0.15
        factors['content_signals'] = content_score
        
        # Length/depth (0-0.2)
        length_score = min(source.word_count / 2000, 1.0) * 0.2
        factors['content_depth'] = length_score
        
        # Source type bonus (0-0.1)
        type_scores = {
            SourceType.ACADEMIC: 0.1,
            SourceType.NEWS: 0.05,
            SourceType.WEBPAGE: 0.02,
            SourceType.BLOG: 0.0,
            SourceType.UNKNOWN: 0.0,
        }
        type_score = type_scores.get(source.source_type, 0.0)
        factors['source_type'] = type_score
        
        # Calculate total
        total_score = sum(factors.values())
        
        source.credibility_score = min(total_score, 1.0)
        source.credibility_factors = factors
        
        return source
    
    def _score_domain(self, domain: str) -> float:
        """Score domain credibility (0-0.4)."""
        domain_lower = domain.lower()
        
        # Check trusted domains
        for trusted in self.TRUSTED_DOMAINS:
            if trusted in domain_lower:
                if trusted in ['.edu', '.gov', 'wikipedia.org']:
                    return 0.4
                return 0.35
        
        # Check low-quality indicators
        for low_qual in self.LOW_QUALITY_INDICATORS:
            if low_qual in domain_lower:
                return 0.1
        
        # Default
        return 0.25
    
    def _calculate_relevance(self, sources: List[Source], query: str) -> List[Source]:
        """Calculate relevance of sources to query."""
        if not sources:
            return sources
        
        # Get query embedding
        query_embedding = self.embedding_model.encode([query])
        
        # Get source embeddings
        source_texts = [
            f"{s.title or ''} {s.text[:1000] if s.text else ''}"
            for s in sources
        ]
        source_embeddings = self.embedding_model.encode(source_texts)
        
        # Calculate similarities
        similarities = cosine_similarity(query_embedding, source_embeddings)[0]
        
        # Update sources with relevance scores
        for source, sim in zip(sources, similarities):
            source.credibility_factors['relevance'] = float(sim)
        
        return sources


# Singleton instance
curator = SourceCurator()
