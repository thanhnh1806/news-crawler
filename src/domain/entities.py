from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse
import re
from datetime import datetime
import os

# Default length limits (can be overridden by config)
DEFAULT_MAX_URL_LENGTH = 500
DEFAULT_MAX_TITLE_LENGTH = 500
DEFAULT_MAX_DESCRIPTION_LENGTH = 2000
DEFAULT_MAX_CONTENT_LENGTH = 50000
DEFAULT_MAX_SOURCE_LENGTH = 100

# Get limits from environment if available
MAX_URL_LENGTH = int(os.getenv("MAX_URL_LENGTH", str(DEFAULT_MAX_URL_LENGTH)))
MAX_TITLE_LENGTH = int(os.getenv("MAX_TITLE_LENGTH", str(DEFAULT_MAX_TITLE_LENGTH)))
MAX_DESCRIPTION_LENGTH = int(os.getenv("MAX_DESCRIPTION_LENGTH", str(DEFAULT_MAX_DESCRIPTION_LENGTH)))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(DEFAULT_MAX_CONTENT_LENGTH)))
MAX_SOURCE_LENGTH = int(os.getenv("MAX_SOURCE_LENGTH", str(DEFAULT_MAX_SOURCE_LENGTH)))


def _validate_url(url: str) -> str:
    """Validate URL format and return it if valid.

    Args:
        url: The URL string to validate.

    Returns:
        The validated URL string.

    Raises:
        ValueError: If the URL is invalid or exceeds maximum length.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL exceeds maximum length of {MAX_URL_LENGTH}")
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use HTTP or HTTPS")
        return url
    except Exception as e:
        raise ValueError(f"Invalid URL: {e}")


def _validate_text(text: str, field_name: str, max_length: int) -> str:
    """Validate text field with length limit.

    Args:
        text: The text string to validate.
        field_name: The name of the field for error messages.
        max_length: Maximum allowed length for the text.

    Returns:
        The validated text string.

    Raises:
        ValueError: If the text is not a string or exceeds maximum length.
    """
    if not isinstance(text, str):
        raise ValueError(f"{field_name} must be a string")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
    return text


def _validate_datetime(dt_str: str) -> str:
    """Validate datetime string format.

    Args:
        dt_str: The datetime string to validate.

    Returns:
        The validated datetime string, or empty string if input is empty.

    Raises:
        ValueError: If the datetime is not a string.
    """
    if not dt_str:
        return ""
    if not isinstance(dt_str, str):
        raise ValueError("Datetime must be a string")
    # Try to parse common datetime formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            datetime.strptime(dt_str, fmt)
            return dt_str
        except ValueError:
            continue
    # If no format matches, accept as-is but warn
    return dt_str


@dataclass
class Article:
    """Represents a news article with validation.

    Attributes:
        url: The article URL (validated, must be HTTP/HTTPS).
        title: The article title (validated, max length from env).
        description: The article description (validated, max length from env).
        image_url: The article image URL (validated, max length from env).
        content: The article content (validated, max length from env).
        source: The article source (validated, max length from env).
        published_at: The publication datetime string (validated).
        first_seen_at: The first seen datetime string (validated).
        crawled_at: The crawl datetime string (validated).
    """

    url: str
    title: str
    description: str = ""
    image_url: str = ""
    content: str = ""
    source: str = ""
    published_at: str = ""
    first_seen_at: str = ""
    crawled_at: str = ""

    def __post_init__(self):
        """Validate fields after initialization.

        Raises:
            ValueError: If any field validation fails.
        """
        self.url = _validate_url(self.url)
        self.title = _validate_text(self.title, "title", MAX_TITLE_LENGTH)
        self.description = _validate_text(self.description, "description", MAX_DESCRIPTION_LENGTH)
        self.image_url = _validate_text(self.image_url, "image_url", MAX_URL_LENGTH)
        self.content = _validate_text(self.content, "content", MAX_CONTENT_LENGTH)
        self.source = _validate_text(self.source, "source", MAX_SOURCE_LENGTH)
        self.published_at = _validate_datetime(self.published_at)
        self.first_seen_at = _validate_datetime(self.first_seen_at)
        self.crawled_at = _validate_datetime(self.crawled_at)

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
    """Represents a cryptocurrency price with validation.

    Attributes:
        symbol: The cryptocurrency symbol (validated, uppercase, max 20 chars).
        name: The cryptocurrency name (validated, max 100 chars).
        price: The current price (validated, must be non-negative).
        change_24h: The 24-hour price change percentage (validated).
        market_cap: The market capitalization (validated, must be non-negative).
        image_url: The cryptocurrency image URL (validated, max 500 chars).
    """

    symbol: str
    name: str
    price: float = 0.0
    change_24h: float = 0.0
    market_cap: float = 0.0
    image_url: str = ""

    def __post_init__(self):
        """Validate fields after initialization.

        Raises:
            ValueError: If any field validation fails.
        """
        self.symbol = _validate_text(self.symbol.upper(), "symbol", 20)
        self.name = _validate_text(self.name, "name", 100)
        self.image_url = _validate_text(self.image_url, "image_url", 500)
        if not isinstance(self.price, (int, float)) or self.price < 0:
            raise ValueError("Price must be a non-negative number")
        if not isinstance(self.change_24h, (int, float)):
            raise ValueError("Change 24h must be a number")
        if not isinstance(self.market_cap, (int, float)) or self.market_cap < 0:
            raise ValueError("Market cap must be a non-negative number")

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
