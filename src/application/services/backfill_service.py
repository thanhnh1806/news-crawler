"""Backfill images use case — updates articles with missing images.
Only depends on domain + outbound ports."""
from typing import List

try:
    from src.domain.entities import Article
    from src.application.ports.outbound.outbound_ports import IWebCrawler, IArticleRepository
except ImportError:
    from domain.entities import Article
    from application.ports.outbound.outbound_ports import IWebCrawler, IArticleRepository


class BackfillImagesUseCase:
    """Backfill missing images for articles."""

    def __init__(self, crawler: IWebCrawler, repository: IArticleRepository):
        self._crawler = crawler
        self._repository = repository

    def execute(self, max_workers: int = 4, limit: int = 9999) -> List[Article]:
        """Get recent articles, backfill images, return updated list."""
        articles = self._repository.get_recent(limit)
        return self._crawler.backfill_images(articles, max_workers=max_workers, limit=limit)
