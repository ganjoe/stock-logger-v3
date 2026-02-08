from typing import List, Dict, Optional
from dataclasses import dataclass

# Import from py_datafetcher
from py_datafetcher import DataFetcherService

@dataclass
class PriceMetadata:
    isin: str
    symbol: str  # Ticker used for fetching
    price: float
    currency: str
    last_update: str  # YYYY-MM-DD
    source: str       # e.g. "Cache" or "Live"

class PortfolioPriceService:
    def __init__(self):
        # Use the central DataFetcherService
        self.fetcher = DataFetcherService()

    def get_cached_prices(self, isins: List[str]) -> Dict[str, PriceMetadata]:
        """
        Loads the current market prices via DataFetcherService.
        By default, this stays in "Offline/Cache" mode unless DataFetcherService
        is configured differently, but we use it here for transparent data access.
        """
        results = {}
        for isin in isins:
            if not isin:
                continue
            
            # get_asset by default checks cache. 
            # If we wanted to allow passive background updates here, we could, 
            # but for a fast UI listing we stick to what's available.
            asset = self.fetcher.get_asset(isin)
            
            if asset:
                results[isin] = PriceMetadata(
                    isin=asset.isin,
                    symbol=asset.symbol,
                    price=asset.market_price,
                    currency=asset.currency,
                    last_update=asset.last_update,
                    source="Service"
                )
        return results
