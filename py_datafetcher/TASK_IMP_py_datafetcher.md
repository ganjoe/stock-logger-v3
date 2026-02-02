# IMPLEMENTATION PLAN: py_datafetcher

## PART 1: The System Skeleton (Shared Context)

The following skeletal code defines the data structures and interfaces required for the `py_datafetcher` module. This structure ensures type safety and clear contracts between components, specifically catering to the error logging and split handling requirements.

```python
# py_datafetcher/types.py
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Protocol
from datetime import date

class ProviderType(Enum):
    YAHOO = "yahoo"
    # ALPHA_VANTAGE = "alpha_vantage" # reserved

@dataclass
class OHLCV:
    date: str # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int

@dataclass
class AssetData:
    isin: str
    symbol: str # The ticker used to fetch data
    currency: str
    market_price: float # Latest price (Realtime or EOD)
    last_update: str # YYYY-MM-DD
    history: Dict[str, OHLCV] = field(default_factory=dict)

@dataclass
class FxData:
    pair: str # e.g. "USDEUR"
    rate: float
    last_update: str # YYYY-MM-DD
    history: Dict[str, float] = field(default_factory=dict)

class DataFetcherError(Exception):
    """Base exception for data fetching errors."""
    pass

@dataclass
class FetchResult:
    symbol: str
    success: bool
    error_message: Optional[str] = None

# Interface for Providers
class IDataProvider(Protocol):
    def fetch_asset_history(self, ticker: str, start_date: date) -> List[OHLCV]:
        """
        Fetches historical data.
        Must handle auto-adjustment for splits (F-DF-080).
        Raises DataFetcherError on failure.
        """
        ...

    def fetch_current_price(self, ticker: str) -> float:
        """
        Fetches the current market price.
        Raises DataFetcherError on failure.
        """
        ...
        
    def fetch_fx_history(self, pair: str, start_date: date) -> Dict[str, float]:
        """
        Fetches FX history.
        Raises DataFetcherError on failure.
        """
        ...
```

---

## PART 2: Implementation Work Orders

These tasks address the missing functionalities identified in the review, specifically structured error logging (F-DF-060) and split handling via `auto_adjust=True` (F-DF-080).

### Task ID: T-DF-001
**Target File**: `py_datafetcher/provider_yahoo.py`
**Description**: Update `YahooProvider` to enable auto-adjustment for splits as per F-DF-080.
**Context**: Uses `IDataProvider` interface and `OHLCV` dataclass.
**Code Stub**:
```python
class YahooProvider(IDataProvider):
    def fetch_asset_history(self, ticker: str, start_date: date) -> List[OHLCV]:
        # ... logic as before but with auto_adjust=True
        pass
```
**Algo/Logic Steps**:
1.  Initialize `yfinance.Ticker` with the given symbol.
2.  Call `history` method on the ticker object.
3.  **CRITICAL**: Set `auto_adjust=True` in the `history()` call to satisfy F-DF-080.
4.  Iterate over the returned DataFrame.
5.  Convert each row into an `OHLCV` object.
    *   Note: When `auto_adjust=True` is used, Yahoo likely returns 'Close' already adjusted. Ensure mapping is correct.
6.  Return the list of `OHLCV` objects.
7.  Handle exceptions and wrap them in `DataFetcherError`.

### Task ID: T-DF-002
**Target File**: `py_datafetcher/error_logger.py` **(NEW FILE)**
**Description**: Implement a dedicated error logger to persist failed fetches for retry/debugging (F-DF-060).
**Context**: New component.
**Code Stub**:
```python
import csv
import os
from datetime import datetime
from typing import List
from dataclasses import dataclass

@dataclass
class FailedFetch:
    timestamp: str
    ticker: str
    isin: str
    reason: str

class ErrorLogger:
    def __init__(self, output_dir: str, filename: str = "fetch_errors.csv"):
        self.filepath = os.path.join(output_dir, filename)
        self._ensure_header()

    def _ensure_header(self):
        """Creates file with header if it doesn't exist."""
        pass

    def log_failure(self, isin: str, ticker: str, reason: str):
        """Appends a failure record to the CSV."""
        pass
```
**Algo/Logic Steps**:
1.  `__init__`: Construct full path. Call `_ensure_header`.
2.  `_ensure_header`: Check if file exists. If not, write header row: `Timestamp,ISIN,Ticker,Reason`.
3.  `log_failure`:
    *   Get current timestamp (ISO format).
    *   Clean inputs (remove newlines from reason to avoid breaking CSV).
    *   Append a new line to the CSV file with `timestamp, isin, ticker, reason`.
    *   Ensure file operations are safe (e.g. use `a` mode).

### Task ID: T-DF-003
**Target File**: `py_datafetcher/fetcher_core.py`
**Description**: Integrate `ErrorLogger` into `FetcherOrchestrator` to log failures when *all* providers fail for an asset.
**Context**: Updates existing `FetcherOrchestrator`.
**Code Stub**:
```python
from .error_logger import ErrorLogger

class FetcherOrchestrator:
    def __init__(self, config: AppConfig, cache: CacheManager, providers: List[IDataProvider], error_logger: ErrorLogger = None):
        # ... existing init ...
        self.error_logger = error_logger

    def update_asset(self, isin: str, ticker: str, start_date_hint: Optional[date] = None) -> bool:
        # ... existing logic ...
        # If all providers fail:
        # self.error_logger.log_failure(...)
        pass
```
**Algo/Logic Steps**:
1.  Update `__init__` to accept an optional `ErrorLogger` instance. Store it.
2.  In `update_asset`:
    *   Keep existing logic for trying providers.
    *   If the loop finishes and `success` is `False`:
        *   Call `self.error_logger.log_failure(isin, ticker, "All providers failed")` (if logger is available).
        *   Log a standard `logging.error` as well (existing behavior).
        *   Return `False`.
    *   If `ticker` is missing/empty:
        *   Call `self.error_logger.log_failure(isin, "UNKNOWN", "No ticker provided")`.
        *   Return `False`.

### Task ID: T-DF-004
**Target File**: `py_datafetcher/datafetcher.py`
**Description**: Wire up the `ErrorLogger` in the main entry point and pass it to the orchestrator.
**Context**: `main()` function updates.
**Code Stub**:
```python
# ... imports ...
from py_datafetcher.error_logger import ErrorLogger

def main():
    # ... setup config, cache ...
    
    # NEW: Init Error Logger
    # config.market_data_dir is a good place, or a specific log dir from config?
    # Requirement says "devidicted log file", placing it in market_data_dir or a 'logs' subdir is standard. 
    # Let's use config.market_data_dir for now or "./logs" if preferred. 
    # Assuming config has a root or similar, we can stick to market_data_dir for visibility.
    error_logger = ErrorLogger(config.market_data_dir)

    orchestrator = FetcherOrchestrator(config, cache, providers, error_logger)

    # ... rest of execution ...
```
**Algo/Logic Steps**:
1.  Import `ErrorLogger`.
2.  Before creating `FetcherOrchestrator`, instantiate `ErrorLogger`. Use `config.market_data_dir` as the target directory so the error log sits next to the data.
3.  Inject `error_logger` into `FetcherOrchestrator`.
4.  Ensure `sys.exit` mapping is appropriate (Warned in reviewer report, but requirement says "Fail-Safe", meaning *process* continues, exit code usually indicates if *job* was clean).
    *   *Self-Correction*: Keep `sys.exit(1)` if failures > 0 to signal the pipeline that intervention is needed, even if the process ran to completion for other assets. This is standard batch job behavior.

