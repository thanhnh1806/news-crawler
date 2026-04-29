"""Inbound ports — interfaces that frameworks call into (use case interfaces)."""
from typing import Protocol, List, Optional, runtime_checkable

try:
    from src.domain.entities import Article, CryptoPrice
except ImportError:
    from domain.entities import Article, CryptoPrice


@runtime_checkable
class ICrawlUseCase(Protocol):
    """Use case: crawl articles from web sources."""

    def execute(self) -> int:
        """Run crawl, return count of new articles."""
        ...


@runtime_checkable
class IDashboardUseCase(Protocol):
    """Use case: generate dashboard HTML."""

    def execute(self, limit: int = 200) -> Optional[str]:
        """Generate dashboard, return HTML path."""
        ...


@runtime_checkable
class ICryptoUseCase(Protocol):
    """Use case: get crypto prices."""

    def execute(self, limit: int = 10) -> Optional[List[CryptoPrice]]:
        """Get top crypto prices."""
        ...
