"""HTTP web crawler adapter — implements IWebCrawler.
Wraps the existing crawler module to conform to the IWebCrawler port.
This is a transitional adapter that delegates to the legacy crawler.py."""
from typing import List

try:
    from src.domain.entities import Article
    from src.application.ports.outbound.outbound_ports import IWebCrawler
except ImportError:
    from domain.entities import Article
    from application.ports.outbound.outbound_ports import IWebCrawler

# Import from legacy crawler module
try:
    from src.crawler import crawl_all as _legacy_crawl_all, backfill_images as _legacy_backfill
except ImportError:
    from crawler import crawl_all as _legacy_crawl_all, backfill_images as _legacy_backfill


class HttpCrawler:
    """Web crawler that delegates to the legacy crawler module.
    Returns Article entity objects instead of raw dicts."""

    def crawl_all(self) -> List[Article]:
        raw_articles = _legacy_crawl_all()
        return [Article.from_dict(a) for a in raw_articles]

    def backfill_images(self, articles: List[Article], max_workers: int = 4, limit: int = 9999) -> List[Article]:
        raw_dicts = [a.to_dict() for a in articles]
        updated = _legacy_backfill(raw_dicts, max_workers=max_workers, limit=limit)
        return [Article.from_dict(a) for a in updated]
