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
