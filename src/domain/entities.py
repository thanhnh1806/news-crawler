from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Article:
    url: str
    title: str
    description: str = ""
    image_url: str = ""
    content: str = ""
    source: str = ""
    published_at: str = ""
    first_seen_at: str = ""
    crawled_at: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "image_url": self.image_url,
            "content": self.content,
            "source": self.source,
            "published_at": self.published_at,
            "first_seen_at": self.first_seen_at,
            "crawled_at": self.crawled_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(
            url=d.get("url", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            image_url=d.get("image_url", ""),
            content=d.get("content", ""),
            source=d.get("source", ""),
            published_at=d.get("published_at", ""),
            first_seen_at=d.get("first_seen_at", ""),
            crawled_at=d.get("crawled_at", ""),
        )


@dataclass
class CryptoPrice:
    symbol: str
    name: str
    price: float = 0.0
    change_24h: float = 0.0
    market_cap: float = 0.0
    image_url: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "change_24h": self.change_24h,
            "market_cap": self.market_cap,
            "image_url": self.image_url,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CryptoPrice":
        return cls(
            symbol=d.get("symbol", ""),
            name=d.get("name", ""),
            price=d.get("price", 0.0),
            change_24h=d.get("change_24h", 0.0),
            market_cap=d.get("market_cap", 0.0),
            image_url=d.get("image_url", ""),
        )
