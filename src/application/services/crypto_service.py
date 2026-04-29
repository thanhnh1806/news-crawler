"""Get crypto prices use case — fetches from crypto client.
Only depends on domain + outbound ports."""
from typing import Optional, List

try:
    from src.domain.entities import CryptoPrice
    from src.application.ports.outbound.outbound_ports import ICryptoClient
except ImportError:
    from domain.entities import CryptoPrice
    from application.ports.outbound.outbound_ports import ICryptoClient


class GetCryptoPricesUseCase:
    """Fetch top cryptocurrency prices."""

    def __init__(self, crypto_client: ICryptoClient):
        self._crypto_client = crypto_client

    def execute(self, limit: int = 10) -> Optional[List[CryptoPrice]]:
        return self._crypto_client.get_top_crypto(limit)
