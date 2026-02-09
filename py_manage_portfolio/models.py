from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PortfolioPosition:
    symbol: str
    isin: str
    quantity: float      # Absolute value
    raw_quantity: float  # Signed value (- for Short)
    direction: str       # "LONG" or "SHORT"
    entry_price: float
    currency: str
    entry_date: Optional[str] = None # ISO format YYYY-MM-DD
    days_held: int = 0
    
    # Market Data
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    
    # Calculated Metrics
    unrealized_pl: Optional[float] = None
    unrealized_pct: Optional[float] = None
    
    # Minervini Metrics
    pos_pct: Optional[float] = None   # % of total equity
    risk_pct: Optional[float] = None  # % of total equity at risk
    dist_pct: Optional[float] = None  # % distance from current price to stop
    
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
    count_ok: int       # Profit (🟢)
    count_warning: int  # Loss or Time (🟡/⏳)
    count_danger: int   # Broken or Missing (🔴/⚠️)


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
    max_position_pct: float # Max Position Size Default 25%
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
