"""Simple Flask server that runs crawl on every page request."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, Response
from crawler import crawl_all, backfill_images
from storage import init_db, insert_article
from generate_dashboard import build_html, get_recent_articles

app = Flask(__name__)


@app.route('/')
def index():
    """Main page that runs crawl on every page request."""
    from datetime import datetime
    
    init_db()
    
    # Run crawl
    print(f"[SERVER] Starting crawl at {datetime.now().strftime('%H:%M:%S')}")
    articles = crawl_all()
    
    # Save to database
    new_count = 0
    for article in articles:
        if insert_article(article):
            new_count += 1
    
    # Backfill images
    articles = backfill_images(articles, max_workers=8, limit=80)
    
    print(f"[SERVER] Crawl complete: {len(articles)} articles, {new_count} new")
    
    # Get recent articles from DB and use shared build_html
    recent = get_recent_articles(200)
    html = build_html(recent)
    
    return Response(html, mimetype='text/html')


@app.route('/api/crawl')
def api_crawl():
    """API endpoint to trigger crawl manually."""
    init_db()
    articles = crawl_all()
    new_count = sum(1 for a in articles if insert_article(a))
    return {'status': 'ok', 'total': len(articles), 'new': new_count}


if __name__ == '__main__':
    print("=" * 60)
    print("News Dashboard Server")
    print("=" * 60)
    print("Open http://localhost:5000 in your browser")
    print("Every refresh will trigger a new crawl!")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
