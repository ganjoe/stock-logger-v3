Architecture & Implementation Plan: Trade Analysis System v2
Role: Senior Software Architect Input: 
alm_portfolio-history.csv

PART 1: The System Skeleton (Shared Context)
This section defines the core data structures (
alm_types.py
) that will be used across the system. All components must import from here.

# alm_types.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal
class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"
    DIVIDEND = "DIVIDEND" # [NEW]
@dataclass
class RawEvent:
    """Represents a single raw event parsed from XML."""
    event_id: str
    timestamp: datetime
    type: TransactionType
    symbol: Optional[str] = None
    currency: str = "EUR"
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")       # For transfers AND dividends
    commission: Decimal = Decimal("0")
    proceeds: Decimal = Decimal("0")
@dataclass
class ProcessedEvent:
    """Final output object for CSV writing."""
    event_id: str
    date: datetime
    type: TransactionType
    symbol: Optional[str]
    
    # Trade specific
    quantity: Decimal = Decimal("0")
    entry_price: Decimal = Decimal("0")
    exit_price: Decimal = Decimal("0")
    fx_rate: Decimal = Decimal("1.0")
    
    # Metrics (Non-cumulative)
    pnl: Decimal = Decimal("0")         # Realized PnL (Trading)
    equity_change: Decimal = Decimal("0") # Cash impact (Trade PnL or Transfer Amount or Dividend)
    
    # Portfolio Metrics (Cumulative)
    total_equity: Decimal = Decimal("0")
    equity_curve: Decimal = Decimal("0") # Trading PnL only
    cum_inflow: Decimal = Decimal("0")   # [NEW] Net Inflow (Deposits - Withdrawals)
    cum_win_rate: float = 0.0
    cum_profit_factor: float = 0.0
    drawdown: float = 0.0
@dataclass
class PortfolioState:
    """Holds the running state for cumulative calculations."""
    total_equity: Decimal = Decimal("0")
    cum_trading_pnl: Decimal = Decimal("0")
    cum_inflow: Decimal = Decimal("0")   # [NEW]
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")
    wins: int = 0
    losses: int = 0
    equity_high_watermark: Decimal = Decimal("0")
    
    # FIFO State: Map Symbol -> List of open (price, date, qty, fx_rate) tuples
    open_positions: Dict[str, List[Any]] = field(default_factory=dict) 
class MarketDataProvider:
    """Abstract Interface for FX data."""
    def get_fx_rate(self, currency_pair: str, date_str: str) -> Decimal:
        raise NotImplementedError
PART 2: Implementation Work Orders (Prompts for Junior Agents)
Task 1: Update Type Definitions
Task ID: T-001 (Update) Target File: 
alm_types.py
 Description: Update 
TransactionType
 to include DIVIDEND. Update 
ProcessedEvent
 and 
PortfolioState
 to include cum_inflow. Context: None Code Stub:

# Update existing file to match the Skeleton in PART 1 EXACTLY.
Algo/Logic Steps:

Add DIVIDEND to 
TransactionType
 enum.
Add cum_inflow: Decimal = Decimal("0") to 
ProcessedEvent
.
Add cum_inflow: Decimal = Decimal("0") to 
PortfolioState
.
Task 2: Update XML Parser
Task ID: T-003 (Update) Target File: 
xml_parser.py
 Description: Add parsing support for <Dividend> tags and ensure robust German number formatting. Context: Uses 
RawEvent
, 
TransactionType
. Code Stub:

def parse_file(self, file_path: str) -> List[RawEvent]:
        # ... existing logic ...
        # Add parsing for Dividends
        pass
    def _parse_dividend_element(self, elem: ET.Element) -> Optional[RawEvent]:
        """ Parses <Dividend> tag. """
        pass
Algo/Logic Steps:

Inside 
parse_file
, add search for Dividend tags (likely under root or unique container). Attempt finding Dividend elements similar to Trades and 
Transaction
.
Implement _parse_dividend_element:
Parse Date (Format DD.MM.YYYY).
Parse Symbol.
Parse Amount (German 1.234,56 -> Decimal).
Parse Currency.
Set type to TransactionType.DIVIDEND.
Return 
RawEvent
.
Ensure 
_parse_german_decimal
 correctly handles strings with . thousands separators and , decimals.
Ensure 
_parse_datetime
 handles DD.MM.YYYY.
Task 3: Update Trade Logic
Task ID: T-004 (Update) Target File: 
trade_logic.py
 Description: Handle DIVIDEND events and update Cum_Inflow metric. Context: Uses 
RawEvent
, 
ProcessedEvent
. Code Stub:

def process_event(self, raw: RawEvent) -> ProcessedEvent:
        if raw.type == TransactionType.DIVIDEND:
            return self._process_dividend(raw)
        # ... rest ...
    def _process_dividend(self, raw: RawEvent) -> ProcessedEvent:
        pass
        
    def _process_transfer(self, raw: RawEvent) -> ProcessedEvent:
        # Update logic to track cum_inflow
        pass
Algo/Logic Steps:

In 
_process_transfer
:
If type == INFLOW, add amount to self.state.cum_inflow.
If type == OUTFLOW, add amount (negative) to self.state.cum_inflow.
Update state.total_equity as before.
Implement _process_dividend:
Treat similar to transfer but does NOT affect cum_inflow (it's internal gain).
Add amount to state.total_equity.
ProcessedEvent.equity_change = amount.
ProcessedEvent.pnl = 0 (per requirements, Dividend is Equity Change but not Trading PnL).
In 
_update_metrics
:
Set processed.cum_inflow = self.state.cum_inflow.
Task 4: Update CSV Writer (Main Script)
Task ID: T-005 (Update) Target File: 
alm_core.py
 Description: Add Cum Inflow column to CSV output. Context: 
ProcessedEvent
 Code Stub:

def write_csv(events: list[ProcessedEvent], filename: str):
    fieldnames = [
        # ... existing ...
        'Cum Inflow',
        # ...
    ]
    # ...
Algo/Logic Steps:

Update fieldnames list to include 'Cum Inflow'.
Update row dictionary to map 'Cum Inflow': f"{ev.cum_inflow:.2f}".
Ensure source format (German) parsing is implicitly handled by xml_parser (verification only).
Ensure target format (Float US) is handled by f"{val:.2f}" (already done).