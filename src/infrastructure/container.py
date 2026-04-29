"""Dependency injection container — wires all layers together.
This is the only file that knows about concrete implementations."""
try:
    from src.infrastructure.config import AppConfig
    from src.adapters.repositories.sqlite_article_repo import SqliteArticleRepository
    from src.adapters.crypto.coingecko_client import CoinGeckoClient
    from src.adapters.web.http_crawler import HttpCrawler
    from src.adapters.web.rate_limiter import DomainRateLimiter
    from src.adapters.renderers.tailwind_renderer import TailwindDashboardRenderer
    from src.application.services.crawl_service import CrawlArticlesUseCase
    from src.application.services.dashboard_service import GenerateDashboardUseCase
    from src.application.services.crypto_service import GetCryptoPricesUseCase
    from src.application.services.backfill_service import BackfillImagesUseCase
    from src.crawler import _normalize_date
except ImportError:
    from infrastructure.config import AppConfig
    from adapters.repositories.sqlite_article_repo import SqliteArticleRepository
    from adapters.crypto.coingecko_client import CoinGeckoClient
    from adapters.web.http_crawler import HttpCrawler
    from adapters.web.rate_limiter import DomainRateLimiter
    from adapters.renderers.tailwind_renderer import TailwindDashboardRenderer
    from application.services.crawl_service import CrawlArticlesUseCase
    from application.services.dashboard_service import GenerateDashboardUseCase
    from application.services.crypto_service import GetCryptoPricesUseCase
    from application.services.backfill_service import BackfillImagesUseCase
    from crawler import _normalize_date


class Container:
    """Manual DI container. Creates and wires all dependencies."""

    def __init__(self, config: AppConfig = None):
        self.config = config or AppConfig()

    # --- Adapters (Layer 3) ---

    @property
    def rate_limiter(self) -> DomainRateLimiter:
        return DomainRateLimiter(min_interval=self.config.rate_limit_interval)

    @property
    def article_repository(self) -> SqliteArticleRepository:
        return SqliteArticleRepository(
            db_path=self.config.db_path,
            normalize_date_fn=_normalize_date,
        )

    @property
    def crypto_client(self) -> CoinGeckoClient:
        return CoinGeckoClient(
            api_url=self.config.coingecko_url,
            cache_ttl=self.config.coingecko_cache_ttl,
        )

    @property
    def web_crawler(self) -> HttpCrawler:
        return HttpCrawler()

    @property
    def dashboard_renderer(self) -> TailwindDashboardRenderer:
        return TailwindDashboardRenderer()

    # --- Use Cases (Layer 2) ---

    @property
    def crawl_use_case(self) -> CrawlArticlesUseCase:
        return CrawlArticlesUseCase(
            crawler=self.web_crawler,
            repository=self.article_repository,
        )

    @property
    def dashboard_use_case(self) -> GenerateDashboardUseCase:
        return GenerateDashboardUseCase(
            repository=self.article_repository,
            crypto_client=self.crypto_client,
            renderer=self.dashboard_renderer,
            dashboard_dir=self.config.dashboard_dir,
            html_path=self.config.html_path,
        )

    @property
    def crypto_use_case(self) -> GetCryptoPricesUseCase:
        return GetCryptoPricesUseCase(crypto_client=self.crypto_client)

    @property
    def backfill_use_case(self) -> BackfillImagesUseCase:
        return BackfillImagesUseCase(
            crawler=self.web_crawler,
            repository=self.article_repository,
        )
