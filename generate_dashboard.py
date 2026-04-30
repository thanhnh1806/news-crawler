import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
HTML_PATH = os.path.join(DASHBOARD_DIR, "index.html")


def get_recent_articles(limit=200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
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
        img_html = f'<img class="w-full aspect-[16/10] object-cover transition-transform duration-300 group-hover:scale-[1.03]" src="{img}" alt="{title}" loading="lazy">'
    else:
        img_html = '<div class="w-full aspect-[16/10] bg-[#F0EEEB] flex items-center justify-center"><span class="text-sm text-[#6C7278] font-mono">IMG</span></div>'

    return f'''<article class="group bg-white rounded-2xl border border-[rgba(226,232,240,0.5)] overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg cursor-pointer">
    <a href="{url}" target="_blank" rel="noopener noreferrer" class="block">
        <div class="overflow-hidden">{img_html}</div>
        <div class="p-5">
            <div class="flex items-center gap-3 mb-3">
                <span class="font-mono text-[11px] uppercase tracking-[0.05em] font-medium text-[#B8422E]">{source.upper()}</span>
                <span class="w-1 h-1 rounded-full bg-[#C4A7A1]"></span>
                <span class="text-xs text-[#6C7278]">{time_str}</span>
            </div>
            <h2 class="text-lg font-semibold text-[#1A1C1E] leading-snug mb-2 group-hover:text-[#B8422E] transition-colors duration-200">{title}</h2>
            <p class="text-sm text-[#6C7278] leading-relaxed line-clamp-2">{desc}</p>
        </div>
    </a>
</article>'''


def render_crypto_sidebar():
    updated_at = datetime.now().strftime("%H:%M %d/%m")
    return f'''<div id="crypto-sidebar" class="bg-white rounded-[20px] border border-[rgba(226,232,240,0.5)] p-6">
        <div class="flex items-center justify-between mb-4 pb-3 border-b border-[rgba(226,232,240,0.5)]">
            <h3 class="font-semibold text-sm text-[#1A1C1E] tracking-tight">Crypto Prices</h3>
            <span id="crypto-updated" class="text-[11px] text-[#6C7278] font-mono">{updated_at}</span>
        </div>
        <div id="crypto-list" class="space-y-1">
            <p class="text-xs text-[#6C7278] italic">Loading prices...</p>
        </div>
    </div>'''


def build_html(articles):
    total = len(articles)
    updated_at = datetime.now().strftime("%H:%M %d/%m/%Y")
    rows_html = "\n".join(render_article_card(a) for a in articles)
    crypto_html = render_crypto_sidebar()

    html = f'''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>Tin Tức Kinh Tế</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, system-ui, sans-serif; background-color: #F7F5F2; }}
        .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
        .line-clamp-2 {{
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        @media (min-width: 1024px) {{
            .layout-2col {{
                display: grid;
                grid-template-columns: 1fr 320px;
                gap: 2.5rem;
                align-items: start;
            }}
            .sidebar-sticky {{
                position: sticky;
                top: 2rem;
            }}
        }}
    </style>
</head>
<body class="text-[#1A1C1E] antialiased min-h-screen">
    <div class="max-w-[1280px] mx-auto px-6 lg:px-8 py-12 lg:py-16">
        <header class="mb-12 lg:mb-16 pb-8 border-b border-[rgba(226,232,240,0.5)]">
            <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
                <div>
                    <h1 class="text-[2.5rem] font-bold tracking-tight text-[#1A1C1E] leading-tight">Tin Tức Kinh Tế</h1>
                    <p class="text-[#6C7278] mt-2 text-base">{total} bài viết · Cập nhật {updated_at}</p>
                </div>
                <div class="text-right">
                    <span class="font-mono text-[11px] uppercase tracking-[0.05em] text-[#6C7278]">Dashboard</span>
                    <p class="font-mono text-sm mt-1 text-[#1A1C1E]">news-crawler</p>
                </div>
            </div>
        </header>

        <div class="layout-2col">
            <main class="grid grid-cols-1 md:grid-cols-2 gap-6">
                {rows_html}
            </main>
            <aside class="sidebar-sticky order-first lg:order-last mb-8 lg:mb-0">
                {crypto_html}
            </aside>
        </div>
    </div>

    <script>
    async function refreshCrypto() {{
        try {{
            const resp = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h');
            const data = await resp.json();
            const list = document.getElementById('crypto-list');
            if (!list) return;

            const rows = data.map(coin => {{
                const price = coin.current_price < 1 ? '$' + coin.current_price.toFixed(6) :
                    coin.current_price < 1000 ? '$' + coin.current_price.toFixed(2) :
                    '$' + coin.current_price.toLocaleString('en', {{maximumFractionDigits: 0}});
                const change = coin.price_change_percentage_24h || 0;
                const changeColor = change >= 0 ? 'text-[#2D6A4F]' : 'text-[#C4A7A1]';
                const sign = change >= 0 ? '+' : '';
                const img = coin.image ? `<img src="${{coin.image}}" alt="${{coin.symbol}}" class="w-7 h-7 rounded-full flex-shrink-0">` :
                    '<div class="w-7 h-7 rounded-full bg-[#F0EEEB] flex-shrink-0"></div>';

                return `<div class="flex items-center gap-3 py-3 border-b border-[rgba(226,232,240,0.5)] last:border-0">
                    ${{img}}
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between">
                            <span class="font-semibold text-sm text-[#1A1C1E]">${{coin.symbol.toUpperCase()}}</span>
                            <span class="text-sm font-medium text-[#1A1C1E] font-mono tabular-nums">${{price}}</span>
                        </div>
                        <div class="flex items-center justify-between mt-0.5">
                            <span class="text-[11px] text-[#6C7278] truncate">${{coin.name}}</span>
                            <span class="text-xs font-medium ${{changeColor}} font-mono tabular-nums">${{sign}}${{change.toFixed(2)}}%</span>
                        </div>
                    </div>
                </div>`;
            }}).join('');

            list.innerHTML = rows;

            const now = new Date();
            const ts = document.getElementById('crypto-updated');
            if (ts) ts.textContent = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0') + ' ' + String(now.getDate()).padStart(2,'0') + '/' + String(now.getMonth()+1).padStart(2,'0');
        }} catch(e) {{ console.warn('Crypto refresh failed', e); }}
    }}

    refreshCrypto();
    setInterval(refreshCrypto, 60000);
    </script>
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
