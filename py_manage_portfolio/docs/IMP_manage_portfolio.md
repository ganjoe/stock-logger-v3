# IMP_manage_portfolio.md (Implementation Plan)

## PART 1: The System Skeleton (Shared Context)

The implementation introduces a new module `py_manage_portfolio.sizer` and extends `py_manage_portfolio.models`.

### Key Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class SizingContext:
    """Snapshot of the current portfolio state."""
    equity: float
    current_exposure: float
    target_exposure_pct: float
    available_budget: float

@dataclass
class TradeParameters:
    """Input parameters for the new trade."""
    symbol: str
    entry_price: float
    stop_loss: float
    risk_pct: float         # Risk of Equity Default 1.0%
    max_position_pct: float # Max Position Size Default 25% (or 10% from csv?)
    one_way_fee: float      # Estimated fee

@dataclass
class SizingResult:
    """The output of the Minervini Sizer Funnel."""
    # Limits
    limit_risk_shares: int
    limit_budget_shares: int
    limit_size_shares: int
    
    # Decision
    suggested_shares: int
    bottleneck: str # "RISK", "BUDGET", "SIZE"
    
    # Metrics for Suggested Quantity
    invested_amount: float
    invested_pct: float
    risk_amount: float
    risk_equity_pct: float
    
    # Scenarios (Net of roundtrip fees)
    price_breakeven: float
    price_2r: float
    price_3r: float
    
    warnings: List[str] = field(default_factory=list)
```

### Interface Skeleton

```python
class MinerviniSizer:
    def __init__(self, project_root: str):
        """Initializes sizer and loads defaults from data_risksettings.csv."""
        pass

    def get_defaults(self) -> Dict:
        """Returns default settings (risk_pct, max_pos_pct, fee, etc.)."""
        pass

    def calculate_wallet_context(self, equity: float, current_exposure: float, target_exposure_pct: float = None) -> SizingContext:
        """Calculates available budget based on targets."""
        pass

    def calculate_sizing(self, context: SizingContext, params: TradeParameters) -> SizingResult:
        """
        The Minervini Funnel: Calculates all limits and determines the bottleneck.
        Returns detailed SizingResult.
        """
        pass
```


## PART 2: Implementation Work Orders

### Task ID: [T-MSM-001]
**Target File**: `py_manage_portfolio/models.py`
**Description**: Define DTOs for Sizing.
**Context**: Used by `MinerviniSizer` and CLI.
**Code Stub**:
```python
@dataclass
class SizingContext:
    equity: float
    current_exposure: float
    target_exposure_pct: float
    available_budget: float

@dataclass
class TradeParameters:
    symbol: str
    entry_price: float
    stop_loss: float
    risk_pct: float
    max_position_pct: float
    one_way_fee: float

@dataclass
class SizingResult:
    limit_risk_shares: int
    limit_budget_shares: int
    limit_size_shares: int
    suggested_shares: int
    bottleneck: str 
    invested_amount: float
    invested_pct: float
    risk_amount: float
    risk_equity_pct: float
    price_breakeven: float
    price_2r: float
    price_3r: float
    warnings: List[str] = field(default_factory=list)
```
**Algo/Logic Steps**:
1. Implement dataclasses.

### Task ID: [T-MSM-002]
**Target File**: `py_manage_portfolio/sizer.py`
**Description**: Implement `MinerviniSizer` class and `__init__`.
**Context**: Loads settings from `data_risksettings.csv`.
**Code Stub**:
```python
import os
import csv
import math
from typing import Dict
from .models import SizingContext, TradeParameters, SizingResult

class MinerviniSizer:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict:
        pass
    
    def get_defaults(self) -> Dict:
        pass
```
**Algo/Logic Steps**:
1. `_load_settings`: Read `data_risksettings.csv`. Parse `default_risk_pct`, `max_pos_size_pct` (default 25.0), `default_fee` (default 2.0).
2. `get_defaults`: Return the loaded dict.

### Task ID: [T-MSM-003]
**Target File**: `py_manage_portfolio/sizer.py`
**Description**: Implement `calculate_sizing` (The Funnel).
**Context**: Core logic for determining share count.
**Code Stub**:
```python
    def calculate_sizing(self, context: SizingContext, params: TradeParameters) -> SizingResult:
        """
        Calculates limits and returns result.
        """
        pass
```
**Algo/Logic Steps**:
1. **Limit 1 (Risk)**: 
   - `RiskBudget = context.equity * (params.risk_pct / 100.0)`
   - `NetRiskBudget = RiskBudget - (2 * params.one_way_fee)` (Roundtrip fee)
   - `RiskPerShare = abs(params.entry_price - params.stop_loss)`
   - `Shares_Risk = floor(NetRiskBudget / RiskPerShare)`
2. **Limit 2 (Budget)**:
   - `Shares_Budget = floor(context.available_budget / params.entry_price)`
3. **Limit 3 (Size Cap)**:
   - `MaxPosValue = context.equity * (params.max_position_pct / 100.0)`
   - `Shares_Size = floor(MaxPosValue / params.entry_price)`
4. **The Funnel**:
   - `suggested = max(0, min(Shares_Risk, Shares_Budget, Shares_Size))`
   - Determine `bottleneck` string based on which limit triggered.
5. **Metrics & Scenarios**:
   - Calculate `invested_amount`, `risk_equity_pct`.
   - `Breakeven = (Invested + 2*Fee) / Shares`
   - `2R = Entry + 2 * (Entry - Stop)` (Simplified, or net of fees? Standard is usually price distance).
   - Return populated `SizingResult`.

### Task ID: [T-MSM-004]
**Target File**: `py_manage_portfolio/manage_stoploss.py`
**Description**: Implement the Wizard UI Step 1 (Portfolio Status).
**Context**: CLI interaction.
**Code Stub**:
```python
def wizard_step_1_get_context(service: PortfolioService, sizer: MinerviniSizer) -> SizingContext:
    # Get live metrics from service
    # Show defaults
    # Ask for overrides (Equity, Exposure, Target%)
    # Return SizingContext
    pass
```

### Task ID: [T-MSM-005]
**Target File**: `py_manage_portfolio/manage_stoploss.py`
**Description**: Implement the Wizard UI Step 2 (Trade Params).
**Context**: CLI interaction.
**Code Stub**:
```python
def wizard_step_2_get_params(service: PortfolioService, sizer: MinerviniSizer) -> TradeParameters:
    # Ask for Ticker
    # Try fetch price (as hint for Entry)
    # Ask Entry, Stop
    # Get defaults from sizer for Risk, MaxPos, Fee
    # Ask overrides
    # Return TradeParameters
    pass
```

### Task ID: [T-MSM-006]
**Target File**: `py_manage_portfolio/manage_stoploss.py`
**Description**: Implement Step 3 (Analysis) and Step 4 (Summary/Commit).
**Context**: Displays the funnel, allows override, and adds to paper trades.
**Code Stub**:
```python
def run_sizing_wizard(service: PortfolioService):
    sizer = MinerviniSizer(service.project_root)
    # Step 1
    ctx = wizard_step_1_get_context(service, sizer)
    # Step 2
    params = wizard_step_2_get_params(service, sizer)
    # Step 3
    result = sizer.calculate_sizing(ctx, params)
    # Display "The Funnel"
    # Ask for quantity override
    
    # Step 4
    # Show "PLANUNGSERGEBNIS" Summary
    # Ask to Save to Paper Trading?
    # If yes -> service.add_paper_position(...)
    pass
```
