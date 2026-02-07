# IMPLEMENTATION PLAN: py_portfolio_history

## PART 1: The System Skeleton (Shared Context)

The following skeletal code defines the data structures and interfaces required for the `py_portfolio_history` module, reflecting the new LIFO logic, cumulative metrics, and extended XML output.

```python
# py_portfolio_history/types.py
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class Transaction:
    id: str
    date: datetime
    type: str # BUY, SELL, DIVIDEND, DEPOSIT, WITHDRAWAL
    symbol: str
    isin: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    currency: str

@dataclass
class Position:
    symbol: str
    isin: str
    quantity: Decimal
    avg_entry_price: Decimal # Weighted Average
    current_price: Decimal
    market_value: Decimal
    accumulated_fees: Decimal
    realized_pnl: Decimal # LIFO realized PnL for this position
    holding_days: int
    currency: str
    
    # Tranches for LIFO matching
    tranches: List['Tranche'] = field(default_factory=list)

@dataclass
class Tranche:
    date: datetime
    quantity: Decimal
    price: Decimal
    fees: Decimal

@dataclass
class PerformanceMetrics:
    trading_pnl: Decimal # Cumulative
    realized_pnl: Decimal # Cumulative (Trading - Fees)
    accounting_pnl: Decimal # Cumulative (Real + FX + Divs)
    fees_total: Decimal # Cumulative
    inflows_total: Decimal # Cumulative (Deposits + Dividends)
    
    # KPIs
    win_rate: float
    profit_factor: float
    expectancy: float
    
    # Trade Stats
    closed_trades_count: int
    open_positions_count: int
    total_transactions_count: int

@dataclass
class PortfolioSnapshot:
    date: datetime
    cash: Decimal
    invested: Decimal # Market Value Exposure
    market_value_total: Decimal
    total_equity: Decimal
    inflows: Decimal
    performance: PerformanceMetrics
    positions: Dict[str, Position]
```

---

## PART 2: Implementation Work Orders

These tasks implement the logic changes requested (LIFO, Dividends as Inflows, Extended Stats).

### Task ID: T-PH-001
**Target File**: `py_portfolio_history/calculator.py`
**Description**: Refactor PnL Calculator to use LIFO matching instead of FIFO.
**Context**: Replaces existing FIFO logic.
**Code Stub**:
```python
class PnlCalculator:
    def process_trade(self, portfolio: PortfolioState, trade: Transaction) -> None:
        """
        Processes a trade using LIFO matching.
        """
        # TODO: Implement LIFO logic
        pass
```
**Algo/Logic Steps**:
1.  **Buy**: Append a new `Tranche` to the `Position.tranches` list. Update `avg_entry_price` (check F-CALC-150).
2.  **Sell**:
    *   Iterate `Position.tranches` in **REVERSE** order (LIFO).
    *   Match sell quantity against tranche quantity.
    *   Calculate PnL: `(SellPrice - TranchePrice) * MatchedQty`.
    *   Reduce tranche quantity or remove tranche if fully closed.
    *   Continue until sell quantity is filled.
3.  **Validation**: Ensure Short-Selling logic handles LIFO correctly (reverse logic: Cover closes last Short).

### Task ID: T-PH-002
**Target File**: `py_portfolio_history/calculator.py`
**Description**: Update Metric Calculation for Inflows and Invested definition.
**Context**: F-LOGIC-026 (Divs as Inflows) and F-CALC-070 (Invested = Exposure).
**Code Stub**:
```python
class MetricCalculator:
    def update_snapshot_metrics(self, state: PortfolioState, event: Transaction) -> PortfolioSnapshot:
        """
        Updates portfolio metrics for a snapshot.
        """
        pass
```
**Algo/Logic Steps**:
1.  **Invested**: Sum `market_value` of all open items in `state.positions`. Do NOT use cost basis.
2.  **Inflows**:
    *   If event is `DEPOSIT`: `inflows += amount`.
    *   If event is `DIVIDEND`: `inflows += amount` (NEW RULE F-LOGIC-026).
    *   If event is `WITHDRAWAL`: `inflows -= amount`.
3.  **Cumulative Fields**: Ensure `trading_pnl`, `fees`, `inflows` are strictly additive over time.

### Task ID: T-PH-003
**Target File**: `py_portfolio_history/xml_generator.py`
**Description**: Extend XML generation to include `<TotalTrades>` block.
**Context**: F-CALC-130 / ICD-CALC-020.
**Code Stub**:
```python
class XmlGenerator:
    def _create_performance_node(self, metrics: PerformanceMetrics) -> ET.Element:
        """ Creates the <Performance> node with new TotalTrades children. """
        pass
```
**Algo/Logic Steps**:
1.  Create `<Performance>` element.
2.  Add existing nodes (`Trading`, `Real`, `Accounting`, `ProfitFactor`...).
3.  **New Block**: Create `<TotalTrades>` element.
4.  Add children:
    *   `<ClosedTrades>` from metrics.
    *   `<OpenPositions>` from metrics.
    *   `<Transactions>` from metrics.
5.  Helper: `metrics.closed_trades_count` needs to be incremented in `calculator.py` whenever a tranche/position is fully closed? Or count of "Round Turn" trades?
    *   *Clarification*: Requirement says "Anzahl vollständig geschlossener Positionen". So if I hold AAPL, buy 10, sell 10 -> ClosedTrades++.

### Task ID: T-PH-004
**Target File**: `py_portfolio_history/portfolio_history.py`
**Description**: Main orchestrator update to wire new components.
**Context**: Integration.
**Code Stub**:
```python
def main():
   # Switch to LIFO calculator
   # Ensure Cache/DataFetcher is reused
   pass
```
**Algo/Logic Steps**:
1.  Ensure `PnlCalculator` is initialized with LIFO strategy.
2.  Verify input parsing handles `is_buy` / `is_sell` correctly for the new LIFO matcher.
