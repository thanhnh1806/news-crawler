import sqlite3
import os
from datetime import datetime
from itertools import groupby
try:
    from src.crypto import get_top_crypto, format_price, format_market_cap
except ImportError:
    from crypto import get_top_crypto, format_price, format_market_cap

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "news.db")
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
HTML_PATH = os.path.join(DASHBOARD_DIR, "index.html")


def get_recent_articles(limit=200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Sort by actual publish date (published_at) or when first seen (first_seen_at)
    # This prevents old articles from appearing at top when recrawled
    c.execute("""
        SELECT url, title, description, image_url, source, published_at, first_seen_at, crawled_at
        FROM articles
        ORDER BY COALESCE(effective_time, first_seen_at, crawled_at) DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
    except Exception:
        return iso


def render_article_card(a):
    url = escape_html(a.get("url", ""))
    title = escape_html(a.get("title", "Không có tiêu đề"))
    desc = escape_html(a.get("description", ""))
    img = escape_html(a.get("image_url", ""))
    source = escape_html(a.get("source", "N/A"))
    time_str = format_time(a.get("published_at") or a.get("first_seen_at") or a.get("crawled_at", ""))

    if img:
        img_html = f'<img class="w-full aspect-video object-cover" src="{img}" alt="{title}" loading="lazy">'
    else:
        img_html = '<div class="w-full aspect-video bg-gray-100 flex items-center justify-center text-xs text-gray-300 font-sans">&mdash;</div>'

    return f'''<article class="group bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
    <a href="{url}" target="_blank" rel="noopener noreferrer" class="block">
        {img_html}
        <div class="p-4">
            <div class="text-xs font-medium uppercase tracking-wider text-blue-600 mb-1.5">{source.upper()}</div>
            <h2 class="font-serif text-lg font-bold text-gray-900 leading-snug mb-1.5 group-hover:text-gray-600 transition-colors">{title}</h2>
            <p class="text-sm text-gray-500 line-clamp-2 mb-2">{desc}</p>
            <div class="text-xs text-gray-400">{time_str}</div>
        </div>
    </a>
</article>'''


def render_crypto_sidebar(coins):
    """Render crypto price sidebar HTML."""
    if not coins:
        return '<p class="text-xs text-gray-400">Không thể tải giá crypto</p>'
    updated_at = datetime.now().strftime("%H:%M %d/%m")
    rows = []
    for c in coins:
        symbol = escape_html(c["symbol"])
        name = escape_html(c["name"])
        price = format_price(c["price"])
        change = c["change_24h"]
        mcap = format_market_cap(c["market_cap"])
        img = escape_html(c.get("image_url", ""))
        change_color = "text-emerald-600" if change >= 0 else "text-red-500"
        change_sign = "+" if change >= 0 else ""
        img_html = f'<img src="{img}" alt="{symbol}" class="w-5 h-5 rounded-full flex-shrink-0">' if img else '<div class="w-5 h-5 rounded-full bg-gray-200 flex-shrink-0"></div>'
        rows.append(f'''<div class="flex items-center gap-2.5 py-2.5 border-b border-gray-50 last:border-0">
            {img_html}
            <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                    <span class="font-semibold text-sm text-gray-900">{symbol}</span>
                    <span class="text-sm font-medium text-gray-900 tabular-nums">{price}</span>
                </div>
                <div class="flex items-center justify-between mt-0.5">
                    <span class="text-[11px] text-gray-400 truncate">{name}</span>
                    <span class="text-xs font-medium {change_color} tabular-nums">{change_sign}{change}%</span>
                </div>
            </div>
        </div>''')
    rows_html = "\n".join(rows)
    return f'''<div id="crypto-sidebar" class="bg-white rounded-lg border border-gray-100 p-4">
        <div class="flex items-center justify-between mb-3 pb-2 border-b border-gray-100">
            <h3 class="font-semibold text-sm text-gray-900">Crypto Prices</h3>
            <span id="crypto-updated" class="text-[10px] text-gray-400">{updated_at}</span>
        </div>
        {rows_html}
    </div>'''


def build_html(articles):
    total = len(articles)
    updated_at = datetime.now().strftime("%H:%M %d/%m/%Y")

    rows_html = "\n".join(render_article_card(a) for a in articles)

    # Fetch crypto prices
    coins = get_top_crypto(10)
    crypto_html = render_crypto_sidebar(coins)

    html = f'''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tin Tức Kinh Tế</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        serif: ['Newsreader', 'Georgia', 'serif'],
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }}
        .line-clamp-2 {{
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        @media (min-width: 1024px) {{
            .layout-2col {{
                display: grid;
                grid-template-columns: 1fr 300px;
                gap: 2rem;
                align-items: start;
            }}
            .sidebar-sticky {{
                position: sticky;
                top: 1.5rem;
            }}
        }}
    </style>
</head>
<body class="bg-white text-gray-900 antialiased">
    <div class="max-w-7xl mx-auto px-6 py-12">
        <header class="mb-12 pb-8 border-b border-gray-100">
            <h1 class="text-3xl font-bold tracking-tight text-gray-900">Tin Tức Kinh Tế</h1>
            <p class="text-gray-500 mt-2 text-base">{total} bài viết · Cập nhật {updated_at}</p>
        </header>

        <div class="layout-2col">
            <main class="grid grid-cols-1 md:grid-cols-2 gap-8">
                {rows_html}
            </main>
            <aside class="sidebar-sticky order-first lg:order-last">
                {crypto_html}
            </aside>
        </div>
    </div>
</body>
</html>'''
    return html


def generate_dashboard(limit=200):
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    articles = get_recent_articles(limit)
    if not articles:
        print("[DASHBOARD] No articles found in database")
        return
    html = build_html(articles)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("[DASHBOARD] Generated " + HTML_PATH + " with " + str(len(articles)) + " articles")
    return HTML_PATH


def open_dashboard():
    import webbrowser
    if os.path.exists(HTML_PATH):
        webbrowser.open("file://" + os.path.abspath(HTML_PATH))
        print("[DASHBOARD] Opened " + HTML_PATH + " in browser")
    else:
        print("[DASHBOARD] HTML not found, run generate_dashboard() first")


if __name__ == "__main__":
    generate_dashboard()
    open_dashboard()
