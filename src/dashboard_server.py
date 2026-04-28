"""Simple Flask server that runs crawl on every page request."""
import sys
import os
import subprocess
import time

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, Response
from crawler import crawl_all, backfill_images
from storage import init_db, insert_article
from generate_dashboard import build_html

app = Flask(__name__)

# HTML template wrapper with auto-refresh
HTML_WRAPPER = '''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="300">  <!-- Auto refresh every 5 minutes as backup -->
    <title>Tin Tức Kinh Tế - Tổng Hợp</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Newsreader:wght@400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #FEF2F2; --card: #FFFFFF; --text: #450A0A; --text-muted: #64748B; --accent: #DC2626; --link: #1E40AF; --border: #FECACA; --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04); --shadow-hover: 0 8px 24px rgba(0,0,0,0.10); }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body { font-family: 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; font-size: 15px; -webkit-font-smoothing: antialiased; }
        .site-header { background: var(--card); border-bottom: 1px solid var(--border); padding: 2rem 1.5rem 1.5rem; position: sticky; top: 0; z-index: 100; }
        .header-inner { max-width: 1200px; margin: 0 auto; }
        .site-title { font-family: 'Newsreader', serif; font-size: 2rem; font-weight: 700; color: var(--text); letter-spacing: -0.02em; line-height: 1.2; }
        .site-meta { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; font-weight: 400; }
        .refresh-banner { background: linear-gradient(90deg, #DC2626, #EF4444); color: white; text-align: center; padding: 0.6rem; font-size: 0.85rem; position: sticky; top: 0; z-index: 101; }
        .refresh-banner a { color: white; text-decoration: underline; font-weight: 500; }
        main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
        .source-section { margin-bottom: 3rem; }
        .section-header { display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: 1.25rem; padding-bottom: 0.5rem; border-bottom: 1.5px solid var(--border); }
        .section-title { font-family: 'Newsreader', serif; font-size: 1.35rem; font-weight: 600; color: var(--accent); letter-spacing: -0.01em; }
        .grid-wrap { margin-top: 1.5rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; }
        .card { display: flex; flex-direction: column; background: var(--card); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); text-decoration: none; color: inherit; transition: transform 0.2s ease, box-shadow 0.2s ease; border: 1px solid transparent; }
        .card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); border-color: var(--border); }
        .card-image-wrap { width: 100%; aspect-ratio: 16 / 10; overflow: hidden; background: #F3F4F6; }
        .card-image { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.3s ease; }
        .card:hover .card-image { transform: scale(1.03); }
        .card-image.placeholder { display: flex; align-items: center; justify-content: center; height: 100%; }
        .card-image.placeholder span { font-size: 0.8rem; color: var(--text-muted); font-weight: 400; }
        .card-body { padding: 1rem 1.1rem 1.1rem; display: flex; flex-direction: column; flex: 1; }
        .card-title { font-family: 'Newsreader', serif; font-size: 1.05rem; font-weight: 600; line-height: 1.35; color: var(--link); margin-bottom: 0.45rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card:hover .card-title { color: var(--accent); }
        .card-desc { font-size: 0.88rem; line-height: 1.55; color: var(--text-muted); margin-bottom: 0.9rem; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; flex: 1; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; margin-top: auto; }
        .source-badge { background: rgba(220,38,38,0.08); color: var(--accent); padding: 0.15rem 0.55rem; border-radius: 999px; font-weight: 500; font-size: 0.72rem; letter-spacing: 0.02em; }
        .card-time { color: var(--text-muted); font-weight: 300; }
        .loading { text-align: center; padding: 3rem 2rem; color: var(--text-muted); }
        .loading-spinner { display: inline-block; width: 40px; height: 40px; border: 3px solid #FECACA; border-top-color: #DC2626; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 1rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) { .site-title { font-size: 1.5rem; } main { padding: 1.25rem 1rem 3rem; } .grid { grid-template-columns: 1fr; gap: 1.25rem; } .section-title { font-size: 1.15rem; } }
        @media (min-width: 769px) and (max-width: 1024px) { .grid { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
    <div class="refresh-banner">
        🔄 Trang tự động cập nhật khi bạn refresh &middot; <a href="/" onclick="location.reload(true); return false;">Refresh ngay</a> để lấy tin mới
    </div>
    <header class="site-header">
        <div class="header-inner">
            <h1 class="site-title">Tin Tức Kinh Tế</h1>
            <p class="site-meta">{meta_text}</p>
        </div>
    </header>
    <main>
        {content}
    </main>
</body>
</html>'''


@app.route('/')
def index():
    """Main page that runs crawl on every request."""
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
    
    # Get recent articles from DB for display
    from generate_dashboard import get_recent_articles
    
    def escape_html(text):
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    def format_time(iso):
        if not iso:
            return ""
        try:
            d = datetime.fromisoformat(iso)
            return d.strftime("%H:%M %d/%m/%Y")
        except:
            return iso
    
    def render_card(a):
        url = escape_html(a.get("url", ""))
        title = escape_html(a.get("title", "Không có tiêu đề"))
        desc = escape_html(a.get("description", ""))
        img = escape_html(a.get("image_url", ""))
        source = escape_html(a.get("source", "N/A"))
        time_str = format_time(a.get("crawled_at", ""))
        
        if img:
            img_html = f'<img class="card-image" src="{img}" alt="{title}" loading="lazy">'
        else:
            img_html = '<div class="card-image placeholder"><span>Không có ảnh</span></div>'
        
        return f'''<a class="card" href="{url}" target="_blank" rel="noopener noreferrer">
    <div class="card-image-wrap">{img_html}</div>
    <div class="card-body">
        <h3 class="card-title">{title}</h3>
        <p class="card-desc">{desc}</p>
        <div class="card-footer">
            <span class="source-badge">{source}</span>
            <span class="card-time">{time_str}</span>
        </div>
    </div>
</a>'''
    
    # Get latest 200 articles from DB (already sorted by crawled_at DESC)
    recent = get_recent_articles(200)
    
    # Render all cards in single grid
    cards = "\n".join(render_card(a) for a in recent)
    content = f'<div class="grid-wrap"><div class="grid">{cards}</div></div>'
    meta = f"Tổng hợp {len(recent)} bài viết &middot; {len(articles)} bài vừa crawl &middot; {new_count} bài mới &middot; Cập nhật {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
    
    html = HTML_WRAPPER.format(content=content, meta_text=meta)
    
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
