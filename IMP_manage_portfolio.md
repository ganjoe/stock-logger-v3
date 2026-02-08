# IMP_manage_portfolio (Implementation Plan)

## PART 1: The System Skeleton (Shared Context)

The implementation will reside in a new file `py_manage_portfolio/service.py` (or potentially split if needed, but likely one file is sufficient for the service logic + DTOs, perhaps `py_manage_portfolio/models.py` for DTOs if strict separation is preferred. For now, we will assume a single module `py_manage_portfolio` with `service.py` exporting the main class and models).

### key Data Structures (Draft)

```python
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

@dataclass
class PortfolioPosition:
    symbol: str
    isin: str
    quantity: float
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: Optional[float]
    market_value: Optional[float]
    unrealized_pl: Optional[float]
    unrealized_pct: Optional[float]
    stop_loss: Optional[float]
    initial_risk: Optional[float]
    r_multiple: Optional[float]
    is_valid: bool
    status_flags: List[str] = field(default_factory=list) # e.g. ["OK"], ["Trail"], ["Missing"]

@dataclass
class PortfolioSummary:
    total_invested: float
    total_unrealized_pl: float
    total_risk: float
    buying_power: float
    equity: float
    position_count: int
    count_ok: int
    count_trail: int
    count_missing: int
```

### Interface Skeleton

```python
class PortfolioService:
    def __init__(self, data_dir: str = "."):
        """
        Initialize with base directory where data files (trades.xml, journal.csv, manual_risk_data.json) reside.
        """
        pass

    def get_open_positions(self, update_prices: bool = False) -> List[PortfolioPosition]:
        """
        Parses trades.xml, loads risk data, fetches current prices (via DataFetcherService or cache),
        calculates all metrics (P&L, Risk, R), and returns a list of PortfolioPosition objects.
        """
        pass

    def get_summary(self) -> PortfolioSummary:
        """
        Calculates the summary based on current open positions and journal data.
        """
        pass
```

## PART 2: Implementation Work Orders

### Task ID: [T-PM-001]
**Target File**: `py_manage_portfolio/models.py`
**Description**: Define the Data Transfer Objects (DTOs) for the Portfolio Service.
**Context**: Used by `PortfolioService` to return structured data.
**Code Stub**:
```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PortfolioPosition:
    symbol: str
    isin: str
    quantity: float      # Absolute value for display/calcs usually, but direction handles sign
    raw_quantity: float  # Signed value (- for Short, + for Long)
    direction: str       # "LONG" or "SHORT"
    entry_price: float
    currency: str
    
    # Market Data
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    
    # Calculated Metrics
    unrealized_pl: Optional[float] = None
    unrealized_pct: Optional[float] = None
    
    # Risk Data
    stop_loss: Optional[float] = None
    initial_risk: Optional[float] = None
    r_multiple: Optional[float] = None
    
    # Status
    is_valid: bool = False
    status_flags: List[str] = field(default_factory=list) # e.g. ["OK", "Trail", "Missing"]

@dataclass
class PortfolioSummary:
    total_invested: float
    total_unrealized_pl: float
    total_risk: float
    
    # From Journal
    buying_power: float
    equity: float
    
    # Counters
    position_count: int
    count_ok: int
    count_trail: int
    count_missing: int
```
**Algo/Logic Steps**:
1. Implement the dataclasses as defined.
2. Ensure types are imported correctly.

### Task ID: [T-PM-002]
**Target File**: `py_manage_portfolio/service.py`
**Description**: Implement the `PortfolioService` class initialization and helper methods for data loading.
**Context**: Connects to `DataFetcherService` and internal parsers.
**Code Stub**:
```python
import os
import json
from typing import List, Dict, Optional, Tuple
from .models import PortfolioPosition, PortfolioSummary
from py_datafetcher.service import DataFetcherService
# Import existing parsers if needed, e.g. from manage_stoploss logic
# For this task, we might need to duplicate or extract logic from manage_stoploss.py 
# OR import form manage_stoploss if it acts as a library (but manage_stoploss has CLI logic).
# BETTER: Re-implement the clean parsing logic here or extract shared logic to a helper. 
# For simplicity in this plan, assume we use the same logic as manage_stoploss but localized here.

class PortfolioService:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.data_fetcher = DataFetcherService() # Wraps the existing DataFetcher
        self.risk_file = os.path.join(project_root, "manual_risk_data.json")
        self.trades_file = os.path.join(project_root, "trades.xml")
        self.journal_file = os.path.join(project_root, "journal.csv")
        
    def _load_risk_data(self) -> Dict:
        """Loads manual_risk_data.json."""
        pass
        
    def _get_journal_metrics(self) -> Tuple[float, float, float]:
        """Returns (equity, cash, total_assets) from journal.csv."""
        pass
```
**Algo/Logic Steps**:
1. `__init__`: Set paths. Initialize `DataFetcherService`.
2. `_load_risk_data`: Check if file exists. parsing JSON. Return dict. Return empty dict if not found.
3. `_get_journal_metrics`: Implement the logic essentially identical to `get_latest_journal_metrics` from the previous turn (read last line of CSV).
    - Open file.
    - Read header to find indices of "Equity", "Cash", "Total_Assets".
    - Read last line.
    - Parse floats.
    - Return (0.0, 0.0, 0.0) if failure.

### Task ID: [T-PM-003]
**Target File**: `py_manage_portfolio/service.py`
**Description**: Implement the core `get_open_positions` logic.
**Context**: This is the heavy lifting, migrating calculation logic from `manage_stoploss.py`.
**Code Stub**:
```python
    def get_open_positions(self, update_prices: bool = False) -> List[PortfolioPosition]:
        """
        Orchestrates the retrieval of positions, prices, and risk data.
        Returns a list of fully populated PortfolioPosition objects.
        """
        # Logic to parse trades.xml (borrow specific logic from manage_stoploss.get_open_positions or xml_parser)
        # For now, let's assume we can import get_open_positions from manage_stoploss or re-implement.
        # Given manage_stoploss is a script, might be better to import from it if possible, 
        # BUT Refactoring rule says: "UI Separation". 
        # Ideally, move `get_open_positions` (the parsing part) to a `common.py` or keep it here.
        # Let's assume we call a helper `_parse_open_positions_from_xml`.
        pass

    def _parse_open_positions_from_xml(self) -> Dict:
         # ... implementation of XML parsing to get {symbol: {qty, tranches...}}
         pass
```
**Algo/Logic Steps**:
1. **Load Data**:
   - Call `_parse_open_positions_from_xml` (logic: use `XmlInputParser`, aggregate `Transaction`s into open positions).
   - Call `_load_risk_data`.
2. **Fetch Prices**:
   - Collect all ISINs from the positions.
   - Call `self.data_fetcher.get_asset(isin, force_update=update_prices)` for each.
   - Store prices in a lookup dict.
3. **Build Positions**:
   - Loop through each open position.
   - Determine `direction`, `quantity` (raw/abs), `avg_entry`.
   - Look up `current_price` from step 2.
   - Look up `stop`, `risk` from risk data dict (using key `SYMBOL_DATE`).
4. **Calculate Metrics**:
   - `market_value` = `abs(qty) * current_price` (or `avg_entry` if no price).
   - `unrealized_pl` = `(current - entry) * raw_qty`.
   - `unrealized_pct` = `((current - entry) / entry) * 100` (logic handles Short direction implicitly via raw_qty sign? No, check formula: For Long: `(Curr-Entry)/Entry`. For Short: `(Entry-Curr)/Entry`. Simplified: `PL / CostBasis`. `CostBasis` = `abs(qty) * entry`. So `PL / (abs(qty)*entry)`.)
   - `r_multiple` = `unrealized_pl / initial_risk` (if risk > 0).
5. **Validation**:
   - Check Stop vs Entry logic (Validation function).
   - Set `status_flags` (OK, Trail, Missing).
6. **Return**: List of `PortfolioPosition` objects.

### Task ID: [T-PM-004]
**Target File**: `py_manage_portfolio/service.py`
**Description**: Implement `get_summary`.
**Context**: Aggregates the list returned by `get_open_positions` and adds Journal data.
**Code Stub**:
```python
    def get_summary(self) -> PortfolioSummary:
        """
        Returns a summary of the portfolio.
        """
        pass
```
**Algo/Logic Steps**:
1. Call `positions = self.get_open_positions(update_prices=False)` (don't force update for summary, use cached).
2. Iterate `positions` to sum:
   - `total_invested` (Sum of `market_value`)
   - `total_unrealized_pl`
   - `total_risk` (Sum of `initial_risk` where present)
   - Count `ok`, `trail`, `missing` based on flags.
3. Call `_get_journal_metrics` to get `equity`, `cash` (buying power), `total_assets`.
4. Construct and return `PortfolioSummary`.
### Task ID: [T-PM-005]  
**Target File**: `py_manage_portfolio/service.py`  
**Description**: Implement `update_stop_loss(symbol, new_stop) -> bool`.  
**Context**: Provides bi-directional write access to risk data.  
**Code Stub**:  
```python
    def update_stop_loss(self, symbol: str, new_stop: float) -> bool:
        """
        Updates the stop loss for an open position.
        1. Finds the open position by symbol to get its start date.
        2. Validates the stop logic.
        3. Calculates initial risk.
        4. Saves to manual_risk_data.json.
        """
        pass
```
**Algo/Logic Steps**:  
1. Call `_parse_open_positions_from_xml()` to find the target position and its `earliest_date`. If not found, return `False`.  
2. Calculate `avg_entry` and `quantity` for that position.  
3. Determine `direction` (Long/Short).  
4. Calculate `initial_risk = abs(avg_entry - new_stop) * float(abs(quantity))`.  
5. Load current `risk_data` using `_load_risk_data()`.  
6. Create/Update entry for `SYMBOL_DATE` with `stop_loss`, `initial_risk`, `symbol`, `entry_date`.  
7. Write back to file using a new helper `_save_risk_data(data)`.  
8. Return `True`.

### Task ID: [T-PM-006]  
**Target File**: `py_manage_portfolio/service.py`  
**Description**: Implement `delete_stop_loss(symbol) -> bool`.  
**Context**: Allows removing risk management data via API.  
**Code Stub**:  
```python
    def delete_stop_loss(self, symbol: str) -> bool:
        """
        Removes the stop loss entry for an open position.
        """
        pass
```
**Algo/Logic Steps**:  
1. Call `_parse_open_positions_from_xml()` to find the target position and its `earliest_date`. If not found, return `False`.  
2. Load current `risk_data`.  
3. Form the key `SYMBOL_DATE`. If it exists in `risk_data`, remove it.  
4. Save the updated `risk_data`.  
5. Return `True`.
