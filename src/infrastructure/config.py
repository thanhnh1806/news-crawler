"""Application configuration — all paths and settings in one place."""
import os
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AppConfig:
    """Centralized application configuration with environment variable support.

    This class provides a single source of truth for all configuration values,
    with defaults that can be overridden via environment variables.

    Attributes:
        project_root: The root directory of the project.
        db_path: Path to the SQLite database file.
        dashboard_dir: Path to the dashboard directory.
        html_path: Path to the dashboard HTML file.
        coingecko_url: CoinGecko API endpoint URL.
        coingecko_cache_ttl: Cache TTL for CoinGecko API responses in seconds.
        coingecko_rate_limit_interval: Minimum interval between CoinGecko API requests in seconds.
        verify_ssl: Whether to verify SSL certificates for HTTPS requests.
        rate_limit_interval: Minimum interval between requests to the same domain in seconds.
        crawl_interval_minutes: Interval between crawl cycles in minutes.
        validate_max_workers: Maximum number of workers for URL validation.
        backfill_max_workers: Maximum number of workers for image backfill.
        max_url_length: Maximum allowed length for URL fields.
        max_title_length: Maximum allowed length for title fields.
        max_description_length: Maximum allowed length for description fields.
        max_content_length: Maximum allowed length for content fields.
        max_source_length: Maximum allowed length for source fields.
    """

    def __init__(self, project_root: str = PROJECT_ROOT):
        """Initialize configuration with environment variable overrides.

        Args:
            project_root: The root directory of the project.
        """
        self.project_root = project_root
        # Database configuration
        self.db_path = os.getenv("DB_PATH", os.path.join(project_root, "news.db"))
        # Dashboard configuration
        self.dashboard_dir = os.getenv("DASHBOARD_DIR", os.path.join(project_root, "dashboard"))
        self.html_path = os.path.join(self.dashboard_dir, "index.html")
        # CoinGecko API configuration
        self.coingecko_url = os.getenv(
            "COINGECKO_URL",
            "https://api.coingecko.com/api/v3/coins/markets"
        )
        self.coingecko_cache_ttl = float(os.getenv("COINGECKO_CACHE_TTL", "2.0"))
        self.coingecko_rate_limit_interval = float(os.getenv("COINGECKO_RATE_LIMIT_INTERVAL", "1.0"))
        self.verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
        # Rate limiting configuration
        self.rate_limit_interval = float(os.getenv("RATE_LIMIT_INTERVAL", "1.0"))
        # Crawler configuration
        self.crawl_interval_minutes = int(os.getenv("CRAWL_INTERVAL_MINUTES", "15"))
        self.validate_max_workers = int(os.getenv("VALIDATE_MAX_WORKERS", "4"))
        self.backfill_max_workers = int(os.getenv("BACKFILL_MAX_WORKERS", "4"))
        # Security configuration
        self.max_url_length = int(os.getenv("MAX_URL_LENGTH", "500"))
        self.max_title_length = int(os.getenv("MAX_TITLE_LENGTH", "500"))
        self.max_description_length = int(os.getenv("MAX_DESCRIPTION_LENGTH", "2000"))
        self.max_content_length = int(os.getenv("MAX_CONTENT_LENGTH", "50000"))
        self.max_source_length = int(os.getenv("MAX_SOURCE_LENGTH", "100"))
