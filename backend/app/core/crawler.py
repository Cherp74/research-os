"""Web crawling functionality."""
import asyncio
import hashlib
import random
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urlparse
import structlog
import httpx
from newspaper import Article
import trafilatura

logger = structlog.get_logger()


# Pool of realistic User-Agent strings (Chrome, Firefox, Safari on various OS)
USER_AGENT_POOL = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]


@dataclass
class CrawledContent:
    """Crawled web content."""
    url: str
    title: Optional[str]
    text: str
    html: Optional[str]
    content_hash: str
    word_count: int
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WebCrawler:
    """Async web crawler with multiple extraction strategies."""

    # Realistic browser User-Agent (Chrome 131 on Windows 11, January 2025)
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # Default headers that mimic a real browser
    DEFAULT_HEADERS = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    # Domains known to be strict about blocking
    STRICT_DOMAINS = {
        "wikipedia.org", "en.wikipedia.org", "wikimedia.org",
        "twitter.com", "x.com",
        "linkedin.com", "www.linkedin.com",
        "facebook.com", "www.facebook.com",
        "instagram.com", "www.instagram.com",
    }

    def __init__(
        self,
        timeout: float = 30.0,
        max_concurrent: int = 10,
        min_delay: float = 0.5,
        max_delay: float = 2.0,
        retry_with_playwright: bool = True,
    ):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.retry_with_playwright = retry_with_playwright
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._last_request_time: Dict[str, float] = {}  # Per-domain rate limiting

        # HTTP client with browser-like headers and cookies
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self.DEFAULT_HEADERS,
            follow_redirects=True,
            http2=True,
            cookies=httpx.Cookies(),  # Enable cookie handling
        )
    
    async def crawl(self, url: str, use_playwright: bool = False) -> CrawledContent:
        """
        Crawl a single URL.

        Args:
            url: URL to crawl
            use_playwright: Use Playwright for JS-heavy sites (slower but more reliable)

        Returns:
            Crawled content
        """
        async with self.semaphore:
            # Apply random delay for rate limiting (per-domain)
            await self._apply_rate_limit(url)

            # Check if domain is known to be strict - prefer Playwright
            domain = self.get_domain(url)
            if any(strict in domain for strict in self.STRICT_DOMAINS):
                use_playwright = True

            if use_playwright:
                return await self._crawl_with_playwright(url)
            else:
                return await self._crawl_with_httpx(url)
    
    async def crawl_multiple(
        self,
        urls: List[str],
        use_playwright: bool = False
    ) -> List[CrawledContent]:
        """
        Crawl multiple URLs in parallel.

        Args:
            urls: List of URLs to crawl
            use_playwright: Use Playwright

        Returns:
            List of crawled content
        """
        tasks = [self.crawl(url, use_playwright) for url in urls]
        return await asyncio.gather(*tasks)

    async def _apply_rate_limit(self, url: str) -> None:
        """Apply per-domain rate limiting with random delays."""
        import time

        domain = self.get_domain(url)
        now = time.time()

        if domain in self._last_request_time:
            elapsed = now - self._last_request_time[domain]
            min_wait = self.min_delay
            if elapsed < min_wait:
                # Add random jitter to the delay
                delay = random.uniform(self.min_delay, self.max_delay)
                logger.debug(f"Rate limiting: waiting {delay:.2f}s for {domain}")
                await asyncio.sleep(delay)

        self._last_request_time[domain] = time.time()

    def _get_request_headers(self, url: str) -> Dict[str, str]:
        """Generate request headers with randomized User-Agent and Referer."""
        headers = self.DEFAULT_HEADERS.copy()

        # Rotate User-Agent
        headers["User-Agent"] = random.choice(USER_AGENT_POOL)

        # Add Referer header (looks like we came from a search engine)
        parsed = urlparse(url)
        domain = parsed.netloc

        # Use realistic referers
        referers = [
            "https://www.google.com/",
            "https://www.google.com/search?q=" + domain.replace(".", "+"),
            "https://duckduckgo.com/",
            "https://www.bing.com/",
        ]
        headers["Referer"] = random.choice(referers)

        # Add Origin header for some sites
        headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"

        return headers
    
    async def _crawl_with_httpx(self, url: str, retry_count: int = 0) -> CrawledContent:
        """Crawl using httpx (fast, for static sites)."""
        try:
            logger.debug(f"Crawling with httpx", url=url, retry=retry_count)

            # Use randomized headers for each request
            headers = self._get_request_headers(url)

            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            html = response.text
            content_hash = hashlib.sha256(html.encode()).hexdigest()[:16]

            # Extract content using multiple strategies
            text, title = self._extract_content(html, url)

            word_count = len(text.split())

            return CrawledContent(
                url=url,
                title=title,
                text=text,
                html=html,
                content_hash=content_hash,
                word_count=word_count,
                success=True,
                metadata={
                    "content_type": response.headers.get("content-type"),
                    "status_code": response.status_code,
                    "method": "httpx",
                }
            )

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.warning(f"HTTP error crawling {url}: {status_code}")

            # Handle 403 Forbidden - retry with Playwright if enabled
            if status_code == 403 and self.retry_with_playwright:
                logger.info(f"Got 403 for {url}, retrying with Playwright")
                return await self._crawl_with_playwright(url)

            # Handle 429 Too Many Requests - exponential backoff retry
            if status_code == 429 and retry_count < 3:
                wait_time = (2 ** retry_count) + random.uniform(1, 3)
                logger.info(f"Got 429 for {url}, waiting {wait_time:.1f}s before retry")
                await asyncio.sleep(wait_time)
                return await self._crawl_with_httpx(url, retry_count + 1)

            # Handle 503 Service Unavailable - quick retry
            if status_code == 503 and retry_count < 2:
                wait_time = random.uniform(2, 5)
                logger.info(f"Got 503 for {url}, waiting {wait_time:.1f}s before retry")
                await asyncio.sleep(wait_time)
                return await self._crawl_with_httpx(url, retry_count + 1)

            return CrawledContent(
                url=url,
                title=None,
                text="",
                html=None,
                content_hash="",
                word_count=0,
                success=False,
                error=f"HTTP {status_code}"
            )
        except httpx.TimeoutException:
            logger.warning(f"Timeout crawling {url}")
            # On timeout, try Playwright as fallback
            if self.retry_with_playwright:
                logger.info(f"Timeout for {url}, retrying with Playwright")
                return await self._crawl_with_playwright(url)
            return CrawledContent(
                url=url,
                title=None,
                text="",
                html=None,
                content_hash="",
                word_count=0,
                success=False,
                error="Timeout"
            )
        except Exception as e:
            logger.warning(f"Error crawling {url}: {e}")
            return CrawledContent(
                url=url,
                title=None,
                text="",
                html=None,
                content_hash="",
                word_count=0,
                success=False,
                error=str(e)
            )
    
    async def _crawl_with_playwright(self, url: str) -> CrawledContent:
        """Crawl using Playwright (slower, for JS-heavy sites and blocked requests)."""
        browser = None
        try:
            logger.debug(f"Crawling with Playwright", url=url)

            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Launch with additional stealth options
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ]
                )

                # Create context with realistic browser fingerprint
                user_agent = random.choice(USER_AGENT_POOL)
                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York",
                    # Accept cookies
                    accept_downloads=False,
                )

                page = await context.new_page()

                # Add stealth script to avoid detection
                await page.add_init_script("""
                    // Override navigator.webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    // Override plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    // Override languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                """)

                try:
                    # Navigate with realistic behavior
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=int(self.timeout * 1000)
                    )

                    # Check for blocked response
                    if response and response.status == 403:
                        logger.warning(f"Playwright also got 403 for {url}")
                        await browser.close()
                        return CrawledContent(
                            url=url,
                            title=None,
                            text="",
                            html=None,
                            content_hash="",
                            word_count=0,
                            success=False,
                            error="HTTP 403 (blocked)",
                            metadata={"method": "playwright"}
                        )

                    # Wait for content to load with random delay
                    await asyncio.sleep(random.uniform(1.5, 3.0))

                    # Scroll slightly to trigger lazy loading
                    await page.evaluate("window.scrollTo(0, 300)")
                    await asyncio.sleep(0.5)

                    html = await page.content()
                    title = await page.title()

                    content_hash = hashlib.sha256(html.encode()).hexdigest()[:16]

                    # Extract text - use trafilatura for better extraction
                    text, extracted_title = self._extract_content(html, url)
                    if not title and extracted_title:
                        title = extracted_title

                    word_count = len(text.split())

                    await browser.close()

                    return CrawledContent(
                        url=url,
                        title=title,
                        text=text,
                        html=html,
                        content_hash=content_hash,
                        word_count=word_count,
                        success=True,
                        metadata={"method": "playwright"}
                    )

                except Exception as e:
                    if browser:
                        await browser.close()
                    raise e

        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
            return CrawledContent(
                url=url,
                title=None,
                text="",
                html=None,
                content_hash="",
                word_count=0,
                success=False,
                error="Playwright not installed"
            )
        except Exception as e:
            logger.warning(f"Playwright error crawling {url}: {e}")
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            # Don't fall back to httpx (would cause infinite loop if called from httpx 403 handler)
            return CrawledContent(
                url=url,
                title=None,
                text="",
                html=None,
                content_hash="",
                word_count=0,
                success=False,
                error=f"Playwright error: {str(e)}"
            )
    
    def _extract_content(self, html: str, url: str) -> tuple[str, Optional[str]]:
        """
        Extract clean text content from HTML using multiple strategies.
        
        Returns:
            Tuple of (text, title)
        """
        text = ""
        title = None
        
        # Strategy 1: Try newspaper3k (good for news articles)
        try:
            article = Article(url)
            article.set_html(html)
            article.parse()
            
            if article.text and len(article.text) > 100:
                text = article.text
                title = article.title
        except Exception:
            pass
        
        # Strategy 2: Try trafilatura (good for general web content)
        if not text or len(text) < 100:
            try:
                extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
                if extracted and len(extracted) > 100:
                    text = extracted
                    
                    # Try to get title from trafilatura
                    if not title:
                        metadata = trafilatura.extract_metadata(html)
                        if metadata:
                            title = metadata.title
            except Exception:
                pass
        
        # Strategy 3: Fallback to basic HTML parsing
        if not text or len(text) < 100:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            
            # Get title
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)
        
        # Clean up text
        text = self._clean_text(text)
        
        return text, title
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit length to avoid memory issues
        max_length = 50000  # ~10k words
        if len(text) > max_length:
            text = text[:max_length] + "\n[Content truncated...]"
        
        return text
    
    def get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()

    @classmethod
    def get_sync_client(cls, timeout: float = 30.0) -> httpx.Client:
        """
        Create a synchronous HTTP client with browser-like headers.

        Use this for any synchronous HTTP requests to ensure consistent
        User-Agent and headers across the codebase.

        Example:
            with WebCrawler.get_sync_client() as client:
                response = client.get("https://example.com")
        """
        return httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers=cls.DEFAULT_HEADERS,
            follow_redirects=True,
            http2=True,
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Singleton instance
crawler = WebCrawler()
