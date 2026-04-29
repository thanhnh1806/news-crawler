"""Crawl articles use case — orchestrates crawling and persistence.
Only depends on domain + outbound ports."""
from typing import List

try:
    from src.domain.entities import Article
    from src.application.ports.outbound.outbound_ports import IWebCrawler, IArticleRepository
except ImportError:
    from domain.entities import Article
    from application.ports.outbound.outbound_ports import IWebCrawler, IArticleRepository


class CrawlArticlesUseCase:
    """Orchestrate: crawl web → persist to repository → return new count."""

    def __init__(self, crawler: IWebCrawler, repository: IArticleRepository):
        self._crawler = crawler
        self._repository = repository

    def execute(self) -> int:
        """Run full crawl pipeline. Returns count of new articles."""
        articles = self._crawler.crawl_all()
        new_count = self._repository.insert_articles_batch(articles)

        total = len(articles)
        print(f"\n[SUMMARY] Total: {total} | New inserted: {new_count}")
        print("=" * 60 + "\n")

        return new_count

    def crawl_and_backfill(self, max_workers: int = 4, limit: int = 9999) -> List[Article]:
        """Crawl, persist, then backfill missing images."""
        articles = self._crawler.crawl_all()
        new_count = self._repository.insert_articles_batch(articles)

        articles = self._crawler.backfill_images(articles, max_workers=max_workers, limit=limit)

        print(f"\n[SUMMARY] Total: {len(articles)} | New inserted: {new_count}")
        return articles
