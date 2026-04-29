"""CoinGecko crypto client — implements ICryptoClient.
Depends on: requests, domain entities."""
import time
import requests
from typing import List, Dict, Optional

try:
    from src.domain.entities import CryptoPrice
except ImportError:
    from domain.entities import CryptoPrice


class CoinGeckoClient:
    """CoinGecko free API client with TTL-based cache."""

    def __init__(self, api_url: str = "https://api.coingecko.com/api/v3/coins/markets", cache_ttl: float = 2.0):
        self._api_url = api_url
        self._cache_ttl = cache_ttl
        self._cache: Dict = {"data": None, "timestamp": 0}

    def get_top_crypto(self, limit: int = 10, currency: str = "usd") -> Optional[List[CryptoPrice]]:
        now = time.time()
        if self._cache["data"] is not None and (now - self._cache["timestamp"]) < self._cache_ttl:
            return self._cache["data"]

        try:
            params = {
                "vs_currency": currency,
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            }
            resp = requests.get(self._api_url, params=params, timeout=15)
            resp.raise_for_status()
            raw = resp.json()

            coins = []
            for c in raw:
                change = c.get("price_change_percentage_24h") or 0
                coins.append(CryptoPrice(
                    symbol=c.get("symbol", "").upper(),
                    name=c.get("name", ""),
                    price=c.get("current_price", 0),
                    change_24h=round(change, 2),
                    market_cap=c.get("market_cap", 0),
                    image_url=c.get("image", ""),
                ))

            self._cache["data"] = coins
            self._cache["timestamp"] = now
            return coins

        except Exception as e:
            print(f"[CRYPTO] Failed to fetch prices: {e}")
            if self._cache["data"] is not None:
                return self._cache["data"]
            return None
