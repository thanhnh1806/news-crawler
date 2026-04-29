"""Outbound ports — interfaces that adapters must implement.
Only depends on domain layer."""
from typing import Protocol, List, Optional, runtime_checkable

try:
    from src.domain.entities import Article, CryptoPrice
except ImportError:
    from domain.entities import Article, CryptoPrice


@runtime_checkable
class IArticleRepository(Protocol):
    """Port for article persistence."""

    def init_db(self) -> None: ...

    def insert_article(self, article: Article) -> bool: ...

    def insert_articles_batch(self, articles: List[Article]) -> int: ...

    def get_recent(self, limit: int = 200) -> List[Article]: ...

    def delete_article(self, url: str) -> bool: ...


@runtime_checkable
class ICryptoClient(Protocol):
    """Port for cryptocurrency price data."""

    def get_top_crypto(self, limit: int = 10, currency: str = "usd") -> Optional[List[CryptoPrice]]: ...


@runtime_checkable
class IWebCrawler(Protocol):
    """Port for web crawling."""

    def crawl_all(self) -> List[Article]: ...

    def backfill_images(self, articles: List[Article], max_workers: int = 4, limit: int = 9999) -> List[Article]: ...


@runtime_checkable
class IDashboardRenderer(Protocol):
    """Port for dashboard HTML rendering."""

    def render_html(self, articles: List[Article], crypto_prices: Optional[List[CryptoPrice]] = None) -> str: ...


@runtime_checkable
class IRateLimiter(Protocol):
    """Port for rate limiting."""

    def wait(self, url: str) -> None: ...
