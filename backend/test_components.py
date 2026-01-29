"""Test script for Research OS components."""
import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.models import Source, Claim
from app.db.database import ResearchDatabase
from app.core.search import search_engine
from app.core.crawler import WebCrawler
from app.core.curator import SourceCurator
from app.core.knowledge_graph import KnowledgeGraph
from app.core.verifier import VerificationEngine


async def test_database():
    """Test database operations."""
    print("\n=== Testing Database ===")
    
    db = ResearchDatabase("data/test.db")
    
    # Create a test source
    source = Source(
        url="https://example.com/test",
        title="Test Article",
        text="This is a test article about AI research.",
        content_hash="abc123",
        credibility_score=0.8
    )
    
    # Save and retrieve
    source_id = db.save_source(source)
    retrieved = db.get_source(source_id)
    
    assert retrieved is not None
    assert retrieved.title == "Test Article"
    print(f"✓ Database: Saved and retrieved source {source_id}")
    
    # Create a test claim
    claim = Claim(
        source_id=source_id,
        text="AI is transforming research.",
        confidence=0.9,
        entities=["AI", "research"]
    )
    
    claim_id = db.save_claim(claim)
    retrieved_claim = db.get_claim(claim_id)
    
    assert retrieved_claim is not None
    assert retrieved_claim.text == "AI is transforming research."
    print(f"✓ Database: Saved and retrieved claim {claim_id}")
    
    return True


async def test_search():
    """Test search functionality."""
    print("\n=== Testing Search ===")
    
    results = await search_engine.search(
        "artificial intelligence latest research",
        max_results=5
    )
    
    print(f"Found {len(results)} results")
    for i, r in enumerate(results[:3]):
        print(f"  {i+1}. {r.title[:50]}... ({r.url[:60]}...)")
    
    assert len(results) > 0
    print("✓ Search: Found results")
    
    return True


async def test_crawler():
    """Test web crawler."""
    print("\n=== Testing Crawler ===")
    
    crawler = WebCrawler()
    
    # Test with a reliable site
    result = await crawler.crawl("https://en.wikipedia.org/wiki/Artificial_intelligence")
    
    print(f"Crawled: {result.url}")
    print(f"Title: {result.title}")
    print(f"Word count: {result.word_count}")
    print(f"Success: {result.success}")
    
    assert result.success
    assert result.word_count > 100
    print("✓ Crawler: Successfully crawled page")
    
    await crawler.close()
    return True


async def test_curation():
    """Test source curation."""
    print("\n=== Testing Curation ===")
    
    curator = SourceCurator()
    
    # Create mock crawled content
    from app.core.crawler import CrawledContent
    
    crawled = [
        CrawledContent(
            url="https://example.com/article1",
            title="Article 1",
            text="This is a research article about machine learning applications.",
            html="<html><body>This is a research article about machine learning applications.</body></html>",
            content_hash="hash1",
            word_count=500,
            success=True
        ),
        CrawledContent(
            url="https://example.com/article2",
            title="Article 2",
            text="Machine learning is transforming many industries with AI applications.",
            html="<html><body>Machine learning is transforming many industries with AI applications.</body></html>",
            content_hash="hash2",
            word_count=600,
            success=True
        ),
        CrawledContent(
            url="https://edu.example.edu/paper",
            title="Academic Paper",
            text="We present a novel approach to machine learning with rigorous methodology.",
            html="<html><body>We present a novel approach to machine learning with rigorous methodology.</body></html>",
            content_hash="hash3",
            word_count=2000,
            success=True
        ),
    ]
    
    result = curator.curate(crawled, "machine learning applications", max_sources=10)
    
    print(f"Curated {len(result.sources)} sources")
    print(f"Removed {result.duplicates_removed} duplicates")
    print(f"Removed {result.low_quality_removed} low quality")
    
    for s in result.sources:
        print(f"  - {s.title}: credibility={s.credibility_score:.2f}")
    
    assert len(result.sources) > 0
    print("✓ Curation: Successfully curated sources")
    
    return True


async def test_knowledge_graph():
    """Test knowledge graph."""
    print("\n=== Testing Knowledge Graph ===")
    
    graph = KnowledgeGraph()
    
    # Create test source and claims
    source = Source(
        id="source1",
        url="https://example.com",
        title="Test Source",
        content_hash="hash1",
        credibility_score=0.8
    )
    
    claim1 = Claim(
        id="claim1",
        source_id="source1",
        text="AI improves efficiency by 30%.",
        confidence=0.9,
        entities=["AI", "efficiency"]
    )
    
    claim2 = Claim(
        id="claim2",
        source_id="source1",
        text="Machine learning reduces costs.",
        confidence=0.8,
        entities=["machine learning", "costs"]
    )
    
    # Add to graph
    graph.add_claim(claim1, source)
    graph.add_claim(claim2, source)
    
    # Get stats
    stats = graph.get_statistics()
    print(f"Graph stats: {stats}")
    
    # Get visualization data
    vis_data = graph.to_vis_data()
    print(f"Nodes: {len(vis_data['nodes'])}, Edges: {len(vis_data['edges'])}")
    
    assert stats['claim_nodes'] == 2
    assert stats['entity_nodes'] >= 2
    print("✓ Knowledge Graph: Successfully built graph")
    
    return True


async def test_verifier():
    """Test verification engine."""
    print("\n=== Testing Verification ===")
    
    verifier = VerificationEngine()
    
    source = Source(
        id="source1",
        url="https://example.com",
        text="Artificial intelligence is transforming research. Studies show 30% improvement in efficiency.",
        content_hash="hash1"
    )
    
    # Test exact match
    claim1 = Claim(
        id="claim1",
        source_id="source1",
        text="Artificial intelligence is transforming research."
    )
    
    verified, method, confidence, excerpt = verifier.verify_claim(claim1, source)
    print(f"Exact match: verified={verified}, method={method}, confidence={confidence:.2f}")
    assert verified
    assert method.value == "exact"
    
    # Test semantic match
    claim2 = Claim(
        id="claim2",
        source_id="source1",
        text="AI is changing how research is conducted."
    )
    
    verified, method, confidence, excerpt = verifier.verify_claim(claim2, source)
    print(f"Semantic match: verified={verified}, method={method}, confidence={confidence:.2f}")
    print("✓ Verification: Successfully verified claims")
    
    return True


async def run_all_tests():
    """Run all component tests."""
    print("=" * 50)
    print("Research OS Component Tests")
    print("=" * 50)
    
    tests = [
        ("Database", test_database),
        ("Search", test_search),
        ("Crawler", test_crawler),
        ("Curation", test_curation),
        ("Knowledge Graph", test_knowledge_graph),
        ("Verification", test_verifier),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
