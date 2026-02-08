
# Implementation Plan: DataFetcher as a Service (IMP_datafetcher_service.md)

## Context
The DataFetcher module is currently a CLI script (`datafetcher.py`) that writes JSON files to disk. The goal is to refactor this into a proper Python Service API (`DataFetcherService`) that can be consumed by other modules (like Portfolio Manager and Dashboard) directly. The service will implement a "Cache-Through" pattern: check cache first, if stale/missing -> fetch online -> update cache -> return data.

## 1. System Skeleton (Shared Context)

### 1.1 Data Models (Exposed API)
Modify `py_datafetcher/data_models.py` to include these definitions.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from datetime import date

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
    last_update: str # ISO Timestamp of last successful fetch
    history: Dict[str, OHLCV] # Key: YYYY-MM-DD

@dataclass
class FxData:
    pair: str # e.g. USDEUR
    rate: float # Current rate
    last_update: str # ISO Timestamp
    history: Dict[str, float] # Key: YYYY-MM-DD -> Rate

class DataFetcherError(Exception):
    """Base exception for DataFetcher service errors."""
    pass
```

### 1.2 Service Interface
New file `py_datafetcher/service.py`.

```python
from typing import Optional
from .data_models import AssetData, FxData

class DataFetcherService:
    def __init__(self, config_path: str = None):
        """
        Initializes the service with configuration, cache manager, and providers.
        """
        pass

    def get_asset(self, isin: str, ticker: str = None, force_update: bool = False) -> Optional[AssetData]:
        """
        Retrieves asset data. 
        1. Checks Cache.
        2. If missing or stale (and ticker provided), fetches from Provider.
        3. Updates Cache.
        4. Returns AssetData.
        """
        pass

    def get_fx(self, pair: str, force_update: bool = False) -> Optional[FxData]:
        """
        Retrieves FX data.
        1. Checks Cache.
        2. If missing or stale, fetches from Provider.
        3. Updates Cache.
        4. Returns FxData.
        """
        pass
```

## 2. Implementation Work Orders

### Task T-001: Extract Orchestrator Logic to Service
**Target File:** `py_datafetcher/service.py`
**Description:** Implement the `DataFetcherService` class. This class effectively replaces and extends the logic currently inside `datafetcher.py` and `fetcher_core.py`'s orchestration. It should instantiate `CacheManager`, `ErrorLogger`, and `Providers`.
**Code Stub:**
```python
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List
from .data_models import AssetData, FxData, AppConfig, ProviderType
from .config_loader import load_config
from .cache_manager import CacheManager
from .error_logger import ErrorLogger
from .provider_yahoo import YahooProvider
from .fetcher_core import FetcherOrchestrator 

class DataFetcherService:
    def __init__(self, config_path: str = None):
        self.config = load_config(config_path) if config_path else load_config()
        self.cache = CacheManager(self.config.market_data_dir)
        self.error_logger = ErrorLogger(self.config.market_data_dir)
        
        # Initialize Providers
        self.providers = []
        for p_conf in self.config.providers:
            if p_conf.name == ProviderType.YAHOO:
                self.providers.append(YahooProvider())
        
        # Reuse Orchestrator for the heavy lifting of fetching/merging?
        # OR better: Refactor logic into this Service to avoid double-wrapping.
        # Let's use the Orchestrator as a helper component for now to minimize code rewrite.
        self.orchestrator = FetcherOrchestrator(self.config, self.cache, self.providers, self.error_logger)

    def get_asset(self, isin: str, ticker: Optional[str] = None, force_update: bool = False) -> Optional[AssetData]:
        """
        Implements Cache-Through pattern.
        """
        # TODO: Implement logic
        pass

    def get_fx(self, pair: str, force_update: bool = False) -> Optional[FxData]:
        """
        Implements Cache-Through pattern for FX.
        """
        # TODO: Implement logic
        pass
```
**Algo/Logic Steps for `get_asset`:**
1. **Cache Attempt:** Call `self.cache.load_asset(isin)`.
2. **Check Stale:** Determine if `asset` is valid. 
   - Rule: Stale if `last_update < today()` OR `asset is None` OR `force_update is True`.
3. **Return Immediate:** If valid and not forced, return `asset`.
4. **Fetch Needed:** If stale/missing:
   - Ensure `ticker` is available (either passed arg or from `asset.symbol`). If not, log error and return existing cached (stale) data or None.
   - Call `self.orchestrator.update_asset(isin, ticker)`.
5. **Reload:** If update successful, reload from cache (`self.cache.load_asset(isin)`) and return.
6. **Fallback:** If update failed, return the stale cached object (better than nothing) or None if truly empty.

### Task T-002: Refactor Orchestrator Return Values (Optional but recommended)
**Target File:** `py_datafetcher/fetcher_core.py`
**Description:** Currently `update_asset` returns `bool`. It might be useful to return the `AssetData` object directly, but for T-001 we can stick to the side-effect (cache update) + reload pattern for simplicity.
**Action:** No changes strictly required to `fetcher_core.py` interface for now if we use reload pattern.

### Task T-003: Update CLI Entry Point
**Target File:** `py_datafetcher/datafetcher.py`
**Description:** Refactor `datafetcher.py` to use `DataFetcherService` instead of manually wiring components. This ensures CLI and Library use the exact same logic.
**Code Stub:**
```python
from py_datafetcher.service import DataFetcherService

def main():
    # ... parse args ...
    
    service = DataFetcherService()
    
    success_count = 0
    fail_count = 0
    
    if args.assets:
        assets_to_fetch = parse_asset_list(args.assets)
        for isin, ticker, _ in assets_to_fetch:
            # We treat CLI run as "Force Update" or at least "Ensure Up To Date"
            result = service.get_asset(isin, ticker, force_update=True)
            if result:
                 success_count += 1
            else:
                 fail_count += 1
                 
    # ... same for FX ...
```

### Task T-004: Expose Service in Package
**Target File:** `py_datafetcher/__init__.py`
**Description:** Export `DataFetcherService` and data models.
**Code Stub:**
```python
from .data_models import AssetData, FxData, OHLCV
from .service import DataFetcherService
```
