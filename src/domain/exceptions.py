"""Domain exceptions — no external dependencies."""


class CrawlError(Exception):
    """Base exception for crawl failures."""
    pass


class RateLimitError(CrawlError):
    """Raised when a rate limit (429) is encountered and retries exhausted."""
    def __init__(self, url: str, status_code: int = 429):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Rate limit hit for {url}: {status_code}")


class StorageError(Exception):
    """Base exception for storage failures."""
    pass


class DuplicateArticleError(StorageError):
    """Raised when attempting to insert a duplicate article."""
    pass
