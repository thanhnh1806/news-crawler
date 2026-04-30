"""Editorial/Financial dashboard renderer."""
from datetime import datetime
from typing import List, Optional

try:
    from src.domain.entities import Article, CryptoPrice
    from src.domain.value_objects import Money, PercentChange
    from src.application.ports.outbound.outbound_ports import IDashboardRenderer
except ImportError:
    from domain.entities import Article, CryptoPrice
    from domain.value_objects import Money, PercentChange
    from application.ports.outbound.outbound_ports import IDashboardRenderer


def _escape_html(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _format_time(iso):
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
        return d.strftime("%H:%M %d/%m/%Y")
    except Exception:
        return iso


class ModernGlassmorphismRenderer:
    """Renders dashboard with editorial/financial design system."""

    def render_html(self, articles: List[Article], crypto_prices: Optional[List[CryptoPrice]] = None) -> str:
        total = len(articles)
        updated_at = datetime.now().strftime("%H:%M %d/%m/%Y")
        version = datetime.now().strftime("%Y%m%d%H%M%S")

        featured_html = self._render_featured(articles[0]) if articles else ""
        grid_html = "\n".join(self._render_article_card(a, i) for i, a in enumerate(articles[1:], start=1))
        crypto_html = self._render_crypto_sidebar(crypto_prices)

        return f'''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="dashboard-version" content="{version}">
    <title>Tin Tức Kinh Tế</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --navy: #0F172A;
            --cream: #FEFDF9;
            --amber: #F59E0B;
            --slate: #334155;
            --muted: #64748B;
            --border: #E2E8F0;
            --card-bg: #FFFFFF;
            --card-shadow: 0 1px 3px rgba(15,23,42,0.06);
            --card-shadow-hover: 0 8px 24px rgba(15,23,42,0.10);
            --radius: 12px;
        }}
        .dark {{
            --navy: #F8FAFC;
            --cream: #0F172A;
            --slate: #94A3B8;
            --muted: #64748B;
            --border: #1E293B;
            --card-bg: #1E293B;
            --card-shadow: 0 1px 3px rgba(0,0,0,0.2);
            --card-shadow-hover: 0 8px 24px rgba(0,0,0,0.25);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: var(--cream);
            color: var(--navy);
            line-height: 1.6;
            font-size: 15px;
            -webkit-font-smoothing: antialiased;
            transition: background 0.3s ease, color 0.3s ease;
        }}
        .site-header {{
            background: var(--card-bg);
            border-bottom: 1px solid var(--border);
            padding: 1.75rem 1.5rem 1.25rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .header-inner {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
        }}
        .site-title {{
            font-family: 'Playfair Display', serif;
            font-size: 2rem;
            font-weight: 700;
            color: var(--navy);
            letter-spacing: -0.02em;
            line-height: 1.2;
        }}
        .site-title .accent {{ color: var(--amber); font-style: italic; }}
        .site-meta {{
            font-size: 0.82rem;
            color: var(--muted);
            margin-top: 0.3rem;
        }}
        .header-actions {{ display: flex; align-items: center; gap: 1rem; }}
        .refresh-indicator {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.78rem;
            color: var(--muted);
            background: rgba(148,163,184,0.08);
            padding: 0.35rem 0.75rem;
            border-radius: 999px;
        }}
        .refresh-dot {{
            width: 6px;
            height: 6px;
            background: #22C55E;
            border-radius: 50%;
            animation: dotPulse 2s ease-in-out infinite;
        }}
        @keyframes dotPulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
        .progress-track {{
            width: 60px;
            height: 3px;
            background: var(--border);
            border-radius: 2px;
            overflow: hidden;
            margin-left: 0.3rem;
        }}
        .progress-fill {{
            height: 100%;
            background: var(--amber);
            border-radius: 2px;
            width: 100%;
            transition: width 1s linear;
        }}
        .theme-toggle {{
            background: transparent;
            border: 1px solid var(--border);
            padding: 0.4rem;
            border-radius: 6px;
            cursor: pointer;
            color: var(--muted);
        }}
        .theme-toggle:hover {{ border-color: var(--amber); color: var(--amber); }}
        main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2.5rem 1.5rem 4rem;
        }}
        .layout {{
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 2.5rem;
            align-items: start;
        }}
        @media (max-width: 1024px) {{ .layout {{ grid-template-columns: 1fr; }} .sidebar {{ order: -1; }} }}
        .sidebar {{
            position: sticky;
            top: 7.5rem;
            align-self: start;
        }}
        .sidebar-card {{
            background: var(--card-bg);
            border-radius: var(--radius);
            padding: 1.25rem;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--border);
        }}
        .sidebar-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 0.75rem;
        }}
        .sidebar-title {{
            font-family: 'Playfair Display', serif;
            font-size: 1rem;
            font-weight: 600;
            color: var(--navy);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .crypto-row {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.6rem 0;
            border-bottom: 1px solid var(--border);
        }}
        .crypto-row:last-child {{ border-bottom: none; }}
        .crypto-icon {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.65rem;
            font-weight: 700;
        }}
        .crypto-info {{ flex: 1; min-width: 0; }}
        .crypto-name-row {{ display: flex; align-items: center; justify-content: space-between; }}
        .crypto-symbol {{ font-weight: 700; font-size: 0.9rem; color: var(--navy); }}
        .crypto-price {{ font-family: monospace; font-size: 0.9rem; font-weight: 600; color: var(--navy); }}
        .crypto-detail-row {{ display: flex; align-items: center; justify-content: space-between; margin-top: 0.15rem; }}
        .crypto-name {{ font-size: 0.75rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .crypto-change {{ font-size: 0.75rem; font-weight: 600; }}
        .crypto-change.up {{ color: #10B981; }}
        .crypto-change.down {{ color: #EF4444; }}
        .featured {{ margin-bottom: 2.5rem; }}
        .featured-card {{
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 2rem;
            background: var(--card-bg);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--border);
            transition: all 0.25s ease;
        }}
        .featured-card:hover {{ box-shadow: var(--card-shadow-hover); }}
        .featured-image-wrap {{ position: relative; overflow: hidden; min-height: 280px; }}
        .featured-image {{ width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; transition: transform 0.5s ease; }}
        .featured-card:hover .featured-image {{ transform: scale(1.03); }}
        .featured-content {{ padding: 1.75rem 1.5rem 1.75rem 0; display: flex; flex-direction: column; justify-content: center; }}
        .featured-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(245,158,11,0.1);
            color: var(--amber);
            padding: 0.3rem 0.75rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            width: fit-content;
            margin-bottom: 1rem;
        }}
        .featured-title {{
            font-family: 'Playfair Display', serif;
            font-size: 1.6rem;
            font-weight: 700;
            line-height: 1.25;
            color: var(--navy);
            margin-bottom: 0.75rem;
        }}
        .featured-card:hover .featured-title {{ color: var(--amber); }}
        .featured-desc {{
            font-size: 0.95rem;
            color: var(--slate);
            line-height: 1.6;
            margin-bottom: 1.25rem;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .featured-meta {{ display: flex; align-items: center; gap: 0.75rem; font-size: 0.8rem; color: var(--muted); }}
        .featured-source {{ background: rgba(15,23,42,0.05); color: var(--navy); padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; }}
        @media (max-width: 768px) {{ .featured-card {{ grid-template-columns: 1fr; }} .featured-image-wrap {{ min-height: 200px; }} .featured-content {{ padding: 1.25rem; }} }}
        .article-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }}
        .article-card {{
            background: var(--card-bg);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--border);
            transition: all 0.25s ease;
            display: flex;
            flex-direction: column;
            text-decoration: none;
            color: inherit;
            animation: cardFadeIn 0.5s ease-out forwards;
            opacity: 1;
        }}
        @keyframes cardFadeIn {{ from {{ opacity: 0; transform: translateY(15px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .article-card:nth-child(1) {{ animation-delay: 0.05s; }}
        .article-card:nth-child(2) {{ animation-delay: 0.1s; }}
        .article-card:nth-child(3) {{ animation-delay: 0.15s; }}
        .article-card:nth-child(4) {{ animation-delay: 0.2s; }}
        .article-card:nth-child(5) {{ animation-delay: 0.25s; }}
        .article-card:nth-child(6) {{ animation-delay: 0.3s; }}
        .article-card:hover {{ box-shadow: var(--card-shadow-hover); transform: translateY(-3px); }}
        .article-image-wrap {{ width: 100%; aspect-ratio: 16/10; overflow: hidden; position: relative; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); }}
        .article-image {{ width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease; }}
        .article-card:hover .article-image {{ transform: scale(1.05); }}
        .article-source-badge {{ position: absolute; top: 0.75rem; left: 0.75rem; background: rgba(15,23,42,0.8); color: white; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; }}
        .article-body {{ padding: 1.1rem; display: flex; flex-direction: column; flex: 1; }}
        .article-title {{ font-family: 'Playfair Display', serif; font-size: 1.05rem; font-weight: 600; line-height: 1.35; color: var(--navy); margin-bottom: 0.5rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
        .article-card:hover .article-title {{ color: var(--amber); }}
        .article-desc {{ font-size: 0.87rem; line-height: 1.55; color: var(--slate); margin-bottom: 0.75rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; flex: 1; }}
        .article-footer {{ display: flex; align-items: center; justify-content: space-between; font-size: 0.76rem; color: var(--muted); margin-top: auto; }}
        @media (prefers-reduced-motion: reduce) {{ .article-card {{ opacity: 1 !important; transform: none !important; animation: none !important; }} }}
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(100,116,139,0.3); border-radius: 4px; }}
    </style>
</head>
<body>
    <header class="site-header">
        <div class="header-inner">
            <div>
                <h1 class="site-title">Tin Tức <span class="accent">Kinh Tế</span></h1>
                <p class="site-meta">{total} bài viết mới nhất · Cập nhật {updated_at}</p>
            </div>
            <div class="header-actions">
                <div class="refresh-indicator">
                    <span class="refresh-dot"></span>
                    <span id="refresh-timer">Tự động cập nhật: 60s</span>
                    <div class="progress-track">
                        <div id="progress-bar" class="progress-fill"></div>
                    </div>
                </div>
                <button class="theme-toggle" id="theme-toggle">
                    <svg id="sun-icon" style="display:none" width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                    <svg id="moon-icon" width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
                </button>
            </div>
        </div>
    </header>
    <main>
        <div class="layout">
            <div class="content">
                {featured_html}
                <div class="article-grid">
                    {grid_html}
                </div>
            </div>
            <aside class="sidebar">
                {crypto_html}
            </aside>
        </div>
    </main>
    <script>
        (function() {{
            const currentVersion = document.querySelector('meta[name="dashboard-version"]')?.content;
            const storedVersion = localStorage.getItem('dashboardVersion');
            if (storedVersion && storedVersion !== currentVersion) {{
                localStorage.setItem('dashboardVersion', currentVersion);
                if (!window.location.search.includes('nocache=')) {{
                    window.location.href = window.location.pathname + '?nocache=' + Date.now();
                    return;
                }}
            }} else {{
                localStorage.setItem('dashboardVersion', currentVersion);
            }}
            if ('serviceWorker' in navigator) {{
                navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
            }}
        }})();
        (function() {{
            const toggle = document.getElementById('theme-toggle');
            const html = document.documentElement;
            const sun = document.getElementById('sun-icon');
            const moon = document.getElementById('moon-icon');
            const saved = localStorage.getItem('theme');
            const isDark = saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches);
            if (isDark) html.classList.add('dark');
            updateIcons();
            toggle?.addEventListener('click', () => {{
                html.classList.toggle('dark');
                localStorage.setItem('theme', html.classList.contains('dark') ? 'dark' : 'light');
                updateIcons();
            }});
            function updateIcons() {{
                const isDark = html.classList.contains('dark');
                sun.style.display = isDark ? 'block' : 'none';
                moon.style.display = isDark ? 'none' : 'block';
            }}
        }})();
        (function() {{
            let timeLeft = 60;
            const timerEl = document.getElementById('refresh-timer');
            const progressEl = document.getElementById('progress-bar');
            setInterval(() => {{
                timeLeft--;
                if (timeLeft <= 0) timeLeft = 60;
                if (timerEl) timerEl.textContent = `Tự động cập nhật: ${{timeLeft}}s`;
                if (progressEl) progressEl.style.width = `${{(timeLeft/60)*100}}%`;
            }}, 1000);
        }})();
    </script>
</body>
</html>'''

    def _render_featured(self, a: Article) -> str:
        url = _escape_html(a.url)
        title = _escape_html(a.title or "Không có tiêu đề")
        desc = _escape_html(a.description or "")
        img = _escape_html(a.image_url or "")
        source = _escape_html(a.source or "N/A")
        time_str = _format_time(a.published_at or a.first_seen_at or a.crawled_at or "")
        img_html = f'<img class="featured-image" src="{img}" alt="{title}" loading="eager">' if img else '<div class="featured-image-wrap" style="background:linear-gradient(135deg,#f1f5f9 0%,#e2e8f0 100%)"></div>'
        return f'''<section class="featured">
    <a href="{url}" target="_blank" rel="noopener noreferrer" class="featured-card">
        <div class="featured-image-wrap">{img_html}</div>
        <div class="featured-content">
            <span class="featured-badge">Nổi bật</span>
            <h2 class="featured-title">{title}</h2>
            <p class="featured-desc">{desc}</p>
            <div class="featured-meta">
                <span class="featured-source">{source.upper()}</span>
                <span>{time_str}</span>
            </div>
        </div>
    </a>
</section>'''

    def _render_article_card(self, a: Article, index: int) -> str:
        url = _escape_html(a.url)
        title = _escape_html(a.title or "Không có tiêu đề")
        desc = _escape_html(a.description or "")
        img = _escape_html(a.image_url or "")
        source = _escape_html(a.source or "N/A")
        time_str = _format_time(a.published_at or a.first_seen_at or a.crawled_at or "")
        img_html = f'<img class="article-image" src="{img}" alt="{title}" loading="lazy">' if img else ''
        return f'''<a href="{url}" target="_blank" rel="noopener noreferrer" class="article-card">
    <div class="article-image-wrap">
        {img_html}
        <span class="article-source-badge">{source.upper()}</span>
    </div>
    <div class="article-body">
        <h3 class="article-title">{title}</h3>
        <p class="article-desc">{desc}</p>
        <div class="article-footer">
            <span>{time_str}</span>
        </div>
    </div>
</a>'''

    def _render_crypto_sidebar(self, coins: Optional[List[CryptoPrice]]) -> str:
        if not coins:
            return '<div class="sidebar-card"><p style="text-align:center;color:var(--muted);padding:1rem 0;">Không thể tải giá crypto</p></div>'
        updated_at = datetime.now().strftime("%H:%M")
        rows = []
        for c in coins:
            symbol = _escape_html(c.symbol)
            name = _escape_html(c.name)
            price = Money(c.price).format_price()
            change = PercentChange(c.change_24h)
            img = _escape_html(c.image_url or "")
            img_html = f'<img src="{img}" alt="{symbol}" style="width:32px;height:32px;border-radius:50%">' if img else f'<span>{symbol[:2]}</span>'
            change_class = 'up' if c.change_24h and c.change_24h >= 0 else 'down'
            rows.append(f'''<div class="crypto-row">
    <div class="crypto-icon">{img_html}</div>
    <div class="crypto-info">
        <div class="crypto-name-row">
            <span class="crypto-symbol">{symbol}</span>
            <span class="crypto-price">{price}</span>
        </div>
        <div class="crypto-detail-row">
            <span class="crypto-name">{name}</span>
            <span class="crypto-change {change_class}">{change.format_with_sign()}</span>
        </div>
    </div>
</div>''')
        rows_html = "".join(rows)
        return f'''<div class="sidebar-card" id="crypto-sidebar">
    <div class="sidebar-header">
        <h3 class="sidebar-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="color:var(--amber)"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
            Crypto Prices
        </h3>
        <span style="font-size:0.75rem;color:var(--muted);display:flex;align-items:center;gap:0.25rem;">
            <span class="refresh-dot"></span>
            {updated_at}
        </span>
    </div>
    {rows_html}
</div>'''
