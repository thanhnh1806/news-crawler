"""Tailwind dashboard renderer — implements IDashboardRenderer.
Depends on: domain entities (for formatting)."""
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


class TailwindDashboardRenderer:
    """Renders dashboard as Tailwind CSS HTML with 2-column layout and crypto sidebar."""

    def render_html(self, articles: List[Article], crypto_prices: Optional[List[CryptoPrice]] = None) -> str:
        total = len(articles)
        updated_at = datetime.now().strftime("%H:%M %d/%m/%Y")

        rows_html = "\n".join(self._render_article_card(a) for a in articles)
        crypto_html = self._render_crypto_sidebar(crypto_prices)

        return f'''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
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
    <script>
    async function refreshCrypto() {{
        try {{
            const resp = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h');
            const data = await resp.json();
            const sidebar = document.getElementById('crypto-sidebar');
            if (!sidebar) return;
            const items = sidebar.querySelectorAll('.flex.items-center.gap-2\\.5');
            data.forEach((coin, i) => {{
                if (i >= items.length) return;
                const price = coin.current_price < 1 ? '$' + coin.current_price.toFixed(6) : coin.current_price < 1000 ? '$' + coin.current_price.toFixed(2) : '$' + coin.current_price.toLocaleString('en', {{maximumFractionDigits: 0}});
                const change = coin.price_change_percentage_24h || 0;
                const color = change >= 0 ? 'text-emerald-600' : 'text-red-500';
                const sign = change >= 0 ? '+' : '';
                const spans = items[i].querySelectorAll('span');
                if (spans[1]) spans[1].textContent = price;
                if (spans[3]) {{ spans[3].textContent = sign + change.toFixed(2) + '%'; spans[3].className = 'text-xs font-medium ' + color + ' tabular-nums'; }}
            }});
            const now = new Date();
            const ts = document.getElementById('crypto-updated');
            if (ts) ts.textContent = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0') + ' ' + String(now.getDate()).padStart(2,'0') + '/' + String(now.getMonth()+1).toString().padStart(2,'0');
        }} catch(e) {{ console.warn('Crypto refresh failed', e); }}
    }}
    setInterval(refreshCrypto, 60000);
    </script>
</body>
</html>'''

    def _render_article_card(self, a: Article) -> str:
        url = _escape_html(a.url)
        title = _escape_html(a.title or "Không có tiêu đề")
        desc = _escape_html(a.description or "")
        img = _escape_html(a.image_url or "")
        source = _escape_html(a.source or "N/A")
        time_str = _format_time(a.published_at or a.first_seen_at or a.crawled_at or "")

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

    def _render_crypto_sidebar(self, coins: Optional[List[CryptoPrice]]) -> str:
        if not coins:
            return '<p class="text-xs text-gray-400">Không thể tải giá crypto</p>'
        updated_at = datetime.now().strftime("%H:%M %d/%m")
        rows = []
        for c in coins:
            symbol = _escape_html(c.symbol)
            name = _escape_html(c.name)
            price = Money(c.price).format_price()
            change = PercentChange(c.change_24h)
            img = _escape_html(c.image_url or "")
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
                    <span class="text-xs font-medium {change.color_class()} tabular-nums">{change.format_with_sign()}</span>
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
