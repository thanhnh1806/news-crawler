"""Value objects — pure domain logic, no external dependencies."""
from dataclasses import dataclass


@dataclass(frozen=True)
class URL:
    """Immutable URL value object."""
    value: str

    def __str__(self) -> str:
        return self.value

    def is_valid(self) -> bool:
        return bool(self.value and self.value.startswith("http"))


@dataclass(frozen=True)
class Money:
    """Immutable money value with formatting logic."""
    amount: float
    currency: str = "USD"

    def format_price(self) -> str:
        if self.amount < 1:
            return f"${self.amount:.6f}"
        elif self.amount < 1000:
            return f"${self.amount:.2f}"
        else:
            return f"${self.amount:,.2f}"

    def format_market_cap(self) -> str:
        if self.amount >= 1e9:
            return f"${self.amount / 1e9:.1f}B"
        elif self.amount >= 1e6:
            return f"${self.amount / 1e6:.0f}M"
        else:
            return f"${self.amount:,.0f}"


@dataclass(frozen=True)
class PercentChange:
    """Immutable percent change with sign formatting."""
    value: float

    @property
    def is_positive(self) -> bool:
        return self.value >= 0

    def format_with_sign(self) -> str:
        sign = "+" if self.is_positive else ""
        return f"{sign}{self.value:.2f}%"

    def color_class(self) -> str:
        return "text-emerald-600" if self.is_positive else "text-red-500"
