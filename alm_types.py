
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal

class TransactionType(Enum):
    BUY = "BUY"       # Quantity > 0 (Long Entry or Short Cover)
    SELL = "SELL"     # Quantity < 0 (Long Exit or Short Entry)
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"
    DIVIDEND = "DIVIDEND"

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
    pnl: Decimal = Decimal("0")         # Realized PnL of this event
    equity_change: Decimal = Decimal("0") # Cash impact (PnL or Transfer Amount)
    
    # Portfolio Metrics (Cumulative)
    total_equity: Decimal = Decimal("0")
    equity_curve: Decimal = Decimal("0") # Trading PnL only
    cum_inflow: Decimal = Decimal("0")   # Net Inflow (Deposits - Withdrawals)
    cum_win_rate: float = 0.0
    cum_profit_factor: float = 0.0
    drawdown: float = 0.0

@dataclass
class PortfolioState:
    """Holds the running state for cumulative calculations."""
    total_equity: Decimal = Decimal("0")
    cum_trading_pnl: Decimal = Decimal("0")
    cum_inflow: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")
    wins: int = 0
    losses: int = 0
    equity_high_watermark: Decimal = Decimal("0") # Kept for Total Equity HWM if needed
    adjusted_equity_high_watermark: Decimal = Decimal("0") # For Clean Drawdown (Excl. Flows)
    
    # FIFO State: Map Symbol -> List of open (price, date, qty, fx_rate) tuples
    # Format of list items: (price: Decimal, date: datetime, qty: Decimal, fx_rate: Decimal)
    open_positions: Dict[str, List[Any]] = field(default_factory=dict) 

class MarketDataProvider:
    """Abstract Interface for FX data."""
    def get_fx_rate(self, currency_pair: str, date_str: str) -> Decimal:
        raise NotImplementedError
