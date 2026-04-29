"""Flask server — replaces dashboard_server.py.
Uses DI container to wire use cases."""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, Response

from infrastructure.config import AppConfig
from infrastructure.container import Container

app = Flask(__name__)
_container: Container = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container(AppConfig())
    return _container


@app.route('/')
def index():
    """Main page that runs crawl on every request."""
    container = get_container()

    print(f"[SERVER] Starting crawl at {datetime.now().strftime('%H:%M:%S')}")
    container.article_repository.init_db()

    # Crawl + persist
    articles = container.web_crawler.crawl_all()
    new_count = container.article_repository.insert_articles_batch(articles)

    # Backfill images
    from application.services.backfill_service import BackfillImagesUseCase
    backfill_uc = BackfillImagesUseCase(
        crawler=container.web_crawler,
        repository=container.article_repository,
    )
    articles = backfill_uc.execute(max_workers=8, limit=80)

    print(f"[SERVER] Crawl complete: {len(articles)} articles, {new_count} new")

    # Generate dashboard HTML
    html = container.dashboard_use_case.execute()
    if html:
        with open(container.config.html_path, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype='text/html')
    return Response("<p>No articles</p>", mimetype='text/html')


@app.route('/api/crawl')
def api_crawl():
    container = get_container()
    container.article_repository.init_db()
    articles = container.web_crawler.crawl_all()
    new_count = container.article_repository.insert_articles_batch(articles)
    return {'status': 'ok', 'total': len(articles), 'new': new_count}


if __name__ == '__main__':
    print("=" * 60)
    print("News Dashboard Server (Clean Architecture)")
    print("=" * 60)
    print("Open http://localhost:5000 in your browser")
    print("Every refresh will trigger a new crawl!")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    container = get_container()
    container.article_repository.init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
