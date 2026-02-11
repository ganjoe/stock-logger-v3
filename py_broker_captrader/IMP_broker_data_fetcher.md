# IMP: Broker DataFetcher Architecture

## Part 1: System Skeleton

The system uses a shared `IBKRConnection` to provide access for both Portfolio Management (`BrokerDataSource`) and Data Fetching (`BrokerDataProvider`).

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

# Shared Connection (Existing) - Reference Only
# class IBKRConnection: ...

@dataclass
class BarData:
    """Standard OHLCV Bar"""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class AbstractDataProvider(ABC):
    """Interface for Data Fetching Providers (to be implemented by BrokerDataProvider)"""
    @abstractmethod
    def get_daily_history(self, symbol: str, days: int = 365) -> List[BarData]:
        pass

    @abstractmethod
    def get_batch_history(self, symbols: List[str], days: int = 365) -> Dict[str, List[BarData]]:
        pass
```

## Part 2: Implementation Work Orders

**Task ID:** [T-008]
**Target File:** `py_broker_captrader/data_provider.py`
**Description:** Implement `BrokerDataProvider` class that fetches historical data from IBKR.
**Context:** Uses `IBKRConnection` (shared instance). Implements `AbstractDataProvider` interface.
**Code Stub:**
```python
class BrokerDataProvider(AbstractDataProvider):
    def __init__(self, connection: IBKRConnection):
        self._connection = connection

    def get_daily_history(self, symbol: str, days: int = 365) -> List[BarData]:
        """
        Fetches daily bars from IBKR.
        Must handle:
        - Contract qualification
        - reqHistoricalData with barSize='1 day', whatToShow='ADJUSTED_LAST'
        - Timeout/Error handling
        """
        # TODO: Implement
        pass

    def get_batch_history(self, symbols: List[str], days: int = 365) -> Dict[str, List[BarData]]:
        """
        Fetches data for multiple symbols respecting pacing constraints (ICD-BRK-010).
        - Max 50 concurrent requests (safe limit)
        - Handle Pacing Violation (Code 162) by waiting
        """
        # TODO: Implement
        pass
```

**Algo/Logic Steps:**
1.  **Contract Qualification:** Use `ib.qualifyContracts()` to ensure symbol is valid.
2.  **Request Construction:** call `ib.reqHistoricalData(contract, endDateTime='', durationStr=f'{days} D', barSizeSetting='1 day', whatToShow='ADJUSTED_LAST', useRTH=True)`.
3.  **Data Conversion:** Convert IB `BarDataList` to internal `BarData` objects.
4.  **Error Handling:** Catch timeouts and specific IB error codes (162, 200). Return empty list on failure.

**Edge Cases:**
- Symbol invalid -> Return empty list, log warning.
- Connection lost -> Raise `ConnectionError`.
- API Pacing Violation -> Implementation should explicitly sleep and retry or limit concurrency.

---
**Input Data:** `icd_broker_captrader.csv` (Requirements)
