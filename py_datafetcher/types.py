from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import date
import json

class ProviderType(Enum):
    YAHOO = "YAHOO"
    ALPHAVANTAGE = "ALPHAVANTAGE"

@dataclass
class ProviderConfig:
    name: ProviderType
    api_key: Optional[str] = None
    priority: int = 1
    rate_limit_ms: int = 1000  # Min time between requests

@dataclass
class AppConfig:
    providers: List[ProviderConfig]
    ticker_map: Dict[str, str] = field(default_factory=dict) # ISIN -> Ticker
    market_data_dir: str = "./data/market"

@dataclass
class OHLCV:
    date: str # ISO YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int

@dataclass
class AssetData:
    isin: str
    symbol: str
    currency: str
    market_price: float # Current/Last Close
    last_update: str # ISO Timestamp
    history: Dict[str, OHLCV] # Key: YYYY-MM-DD

@dataclass
class FxData:
    pair: str # e.g. USDEUR
    rate: float # Current rate
    last_update: str
    history: Dict[str, float] # Key: YYYY-MM-DD -> Rate

class IDataProvider:
    """ Interface for all data providers """
    def fetch_asset_history(self, ticker: str, start_date: date) -> List[OHLCV]:
        raise NotImplementedError
        
    def fetch_current_price(self, ticker: str) -> float:
        raise NotImplementedError
    
    def fetch_fx_history(self, pair: str, start_date: date) -> Dict[str, float]:
        raise NotImplementedError

class DataFetcherError(Exception):
    pass
