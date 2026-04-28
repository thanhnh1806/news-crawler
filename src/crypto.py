"""Fetch cryptocurrency prices from CoinGecko free API."""
import requests
import time
from typing import List, Dict, Optional

_CACHE: Dict = {"data": None, "timestamp": 0}
_CACHE_TTL = 2  # 2 seconds

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"


def format_price(price: float) -> str:
    """Format price with appropriate decimal places."""
    if price < 1:
        return f"${price:.6f}"
    elif price < 1000:
        return f"${price:.2f}"
    else:
        return f"${price:,.0f}"


def format_market_cap(mcap: float) -> str:
    """Format market cap in billions/millions."""
    if mcap >= 1e9:
        return f"${mcap / 1e9:.1f}B"
    elif mcap >= 1e6:
        return f"${mcap / 1e6:.0f}M"
    else:
        return f"${mcap:,.0f}"


def get_top_crypto(limit: int = 10, currency: str = "usd") -> Optional[List[Dict]]:
    """Get top cryptocurrencies by market cap from CoinGecko.
    Results are cached for 5 minutes."""
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["timestamp"]) < _CACHE_TTL:
        return _CACHE["data"]

    try:
        params = {
            "vs_currency": currency,
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        resp = requests.get(COINGECKO_URL, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        coins = []
        for c in raw:
            change = c.get("price_change_percentage_24h") or 0
            coins.append({
                "symbol": c.get("symbol", "").upper(),
                "name": c.get("name", ""),
                "price": c.get("current_price", 0),
                "change_24h": round(change, 2),
                "market_cap": c.get("market_cap", 0),
                "image_url": c.get("image", ""),
            })

        _CACHE["data"] = coins
        _CACHE["timestamp"] = now
        return coins

    except Exception as e:
        print(f"[CRYPTO] Failed to fetch prices: {e}")
        # Return cached data even if expired, better than nothing
        if _CACHE["data"] is not None:
            return _CACHE["data"]
        return None


if __name__ == "__main__":
    coins = get_top_crypto()
    if coins:
        for c in coins:
            change_str = f"+{c['change_24h']}%" if c['change_24h'] >= 0 else f"{c['change_24h']}%"
            print(f"  {c['symbol']:6s} {format_price(c['price']):>12s}  {change_str:>8s}  {format_market_cap(c['market_cap'])}")
    else:
        print("No data")
