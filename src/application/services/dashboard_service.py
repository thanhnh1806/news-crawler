"""Generate dashboard use case — gets recent articles + crypto prices → renders HTML.
Only depends on domain + outbound ports."""
import os
from typing import Optional, List

try:
    from src.domain.entities import Article, CryptoPrice
    from src.application.ports.outbound.outbound_ports import IArticleRepository, ICryptoClient, IDashboardRenderer
except ImportError:
    from domain.entities import Article, CryptoPrice
    from application.ports.outbound.outbound_ports import IArticleRepository, ICryptoClient, IDashboardRenderer


class GenerateDashboardUseCase:
    """Get recent articles + crypto prices → render dashboard HTML → write to file."""

    def __init__(
        self,
        repository: IArticleRepository,
        crypto_client: ICryptoClient,
        renderer: IDashboardRenderer,
        dashboard_dir: str,
        html_path: str,
    ):
        self._repository = repository
        self._crypto_client = crypto_client
        self._renderer = renderer
        self._dashboard_dir = dashboard_dir
        self._html_path = html_path

    def execute(self, limit: int = 200) -> Optional[str]:
        """Generate dashboard HTML file. Returns file path or None."""
        articles = self._repository.get_recent(limit)
        if not articles:
            print("[DASHBOARD] No articles found in database")
            return None

        crypto_prices = self._crypto_client.get_top_crypto(10)
        html = self._renderer.render_html(articles, crypto_prices)

        os.makedirs(self._dashboard_dir, exist_ok=True)
        with open(self._html_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[DASHBOARD] Generated {self._html_path} with {len(articles)} articles")
        return self._html_path
