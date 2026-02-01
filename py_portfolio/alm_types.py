
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any
from datetime import datetime

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"
    DIVIDEND = "DIVIDEND"

@dataclass
class OHLC:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

@dataclass
class Performance:
    trading_pnl: Decimal = Decimal("0")
    real_pnl: Decimal = Decimal("0")
    accounting_pnl: Decimal = Decimal("0")
    profit_factor: float = 0.0 # Portfolio level only
    win_rate: float = 0.0 # Portfolio level only

@dataclass
class Position:
    symbol: str
    quantity: Decimal
    value: Decimal # Market Value
    
    # Detailed fields
    isin: str = ""
    avg_entry_price: Decimal = Decimal("0")
    currency: str = "EUR"
    exchange_rate: Decimal = Decimal("1.0")
    accumulated_fees: Decimal = Decimal("0")
    stop_loss: Decimal = Decimal("0")
    ohlc: Optional[OHLC] = None
    performance: Optional[Performance] = None

@dataclass
class Snapshot:
    inflows: Decimal = Decimal("0")
    cash: Decimal = Decimal("0")
    invested: Decimal = Decimal("0")
    market_value: Decimal = Decimal("0")
    market_value_ohlc: Optional[OHLC] = None
    total_equity: Decimal = Decimal("0")
    performance: Optional[Performance] = None
    positions: List[Position] = field(default_factory=list)

@dataclass
class RawEvent:
    """Represents a single raw event parsed from XML (numbered tag)."""
    event_id: str             # The tag name, e.g., "1", "2"
    timestamp: datetime
    type: TransactionType
    symbol: Optional[str] = None
    currency: str = "EUR"
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")        # For trades
    amount: Decimal = Decimal("0")       # For transfers
    commission: Decimal = Decimal("0")
    proceeds: Decimal = Decimal("0")     # Raw XML proceeds

@dataclass
class TradeMatch:
    """Represents a matched portion of a trade (FIFO)."""
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_date: datetime
    exit_date: datetime
    entry_fx: Decimal
    exit_fx: Decimal
    pnl: Decimal      # Calculated PnL for this specific match chunk

@dataclass
class ProcessedEvent:
    """Final output object for XML writing."""
    event_id: str
    date: datetime
    type: TransactionType
    symbol: Optional[str] = None
    
    # Execution Details
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0") # Raw execution price
    fx_rate: Decimal = Decimal("1.0")
    market_value: Decimal = Decimal("0") # Value of this single transaction
    
    # The complete state AFTER this event
    snapshot: Optional[Snapshot] = None

@dataclass
class PortfolioState:
    """Holds the running state for cumulative calculations."""
    # Cash & Equity
    cash_balance: Decimal = Decimal("0")
    cum_inflow: Decimal = Decimal("0")
    
    # Performance Accumulators
    cum_trading_pnl: Decimal = Decimal("0")
    cum_real_pnl: Decimal = Decimal("0")       # Trading - Fees
    cum_accounting_pnl: Decimal = Decimal("0") # Real + FX logic
    
    # Global Stats
    gross_profit_trading: Decimal = Decimal("0")
    gross_loss_trading: Decimal = Decimal("0")
    wins_trading: int = 0
    losses_trading: int = 0
    
    # High Watermark for Drawdown (based on Total Equity? Or Adjusted?)
    # ICD-CALC-010 doesn't strictly specify Drawdown basis, assuming Clean Total Equity (Equity - Inflow)
    adjusted_equity_high_watermark: Decimal = Decimal("0") 
    
    # FIFO State: Map Symbol -> List of open positions (complex objects now preferred or keeping dicts?)
    # We need to track cost basis and separate fees per position.
    # List item: {'price': Dec, 'date': dt, 'qty': Dec, 'fx': Dec, 'fees_acc': Dec}
    open_positions: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict) 

class MarketDataProvider:
    """Abstract Interface for FX data."""
    def get_fx_rate(self, currency_pair: str, date_str: str) -> Decimal:
        raise NotImplementedError
