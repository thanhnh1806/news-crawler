"""Application configuration — all paths and settings in one place."""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AppConfig:
    """Centralized application configuration."""
    def __init__(self, project_root: str = PROJECT_ROOT):
        self.project_root = project_root
        self.db_path = os.path.join(project_root, "news.db")
        self.dashboard_dir = os.path.join(project_root, "dashboard")
        self.html_path = os.path.join(self.dashboard_dir, "index.html")
        self.coingecko_url = "https://api.coingecko.com/api/v3/coins/markets"
        self.coingecko_cache_ttl = 2.0  # seconds
        self.rate_limit_interval = 1.0  # seconds between requests to same domain
        self.crawl_interval_minutes = 15
        self.validate_max_workers = 4
        self.backfill_max_workers = 4
