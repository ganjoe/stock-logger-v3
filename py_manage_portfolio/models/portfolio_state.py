"""
Unified Portfolio Models.

Position:       Single enriched position (stored + displayed).
PortfolioState: Full portfolio snapshot (serialized to JSON).
PortfolioSummary: Aggregate portfolio metrics for dashboard display.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class Position:
    """
    Unified position model — stored in JSON AND displayed in dashboard.
    
    Core fields (persisted):
        symbol, quantity, entry_price, current_price, currency,
        isin, entry_date, direction, stop_loss, initial_risk
    
    Computed fields (calculated at runtime via @property):
        market_value, unrealized_pnl, unrealized_pct, r_multiple
        
    Injected fields (set by PortfolioService after loading):
        days_held, pos_pct, risk_pct, dist_pct, status_flags
    """
    # Core (always persisted)
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    currency: str = "USD"
    
    # Identity & Context (persisted)
    isin: Optional[str] = None
    entry_date: Optional[str] = None    # ISO YYYY-MM-DD
    direction: str = "LONG"             # "LONG" or "SHORT"
    
    # Risk (persisted)
    stop_loss: Optional[float] = None
    stop_limit_price: Optional[float] = None
    stop_type: str = "STP"              # "STP" (Market) or "STP LMT" (Limit)
    initial_risk: Optional[float] = None
    
    # Injected by Service (not persisted in JSON, set after loading)
    days_held: int = 0
    pos_pct: Optional[float] = None     # % of total equity
    risk_pct: Optional[float] = None    # % of total equity at risk
    dist_pct: Optional[float] = None    # % distance from price to stop
    status_flags: List[str] = field(default_factory=list)

    # --- Computed Properties ---
    
    @property
    def raw_quantity(self) -> float:
        """Signed quantity (negative for SHORT)."""
        return -self.quantity if self.direction == "SHORT" else self.quantity

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def unrealized_pnl(self) -> float:
        if self.direction == "SHORT":
            return (self.entry_price - self.current_price) * self.quantity
        return (self.current_price - self.entry_price) * self.quantity
    
    @property
    def unrealized_pl(self) -> float:
        """Alias for unrealized_pnl."""
        return self.unrealized_pnl
    
    @property
    def unrealized_pct(self) -> Optional[float]:
        if not self.entry_price:
            return None
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100
    
    @property
    def r_multiple(self) -> Optional[float]:
        if not self.stop_loss or not self.initial_risk or self.initial_risk == 0:
            return None
        return self.unrealized_pnl / abs(self.initial_risk)
    
    @property
    def is_valid(self) -> bool:
        """Position has minimum required data."""
        return self.entry_price > 0 and self.quantity > 0


@dataclass
class PortfolioState:
    """Full portfolio snapshot — serialized to/from JSON."""
    timestamp: str  # ISO Format
    cash: float
    equity: float
    positions: Dict[str, Position] = field(default_factory=dict)
    
    def update_timestamp(self):
        self.timestamp = datetime.now().isoformat()
        
    def add_position(self, pos: Position):
        if pos.symbol in self.positions:
            existing = self.positions[pos.symbol]
            total_qty = existing.quantity + pos.quantity
            if total_qty == 0:
                del self.positions[pos.symbol]
            else:
                new_cost = (existing.quantity * existing.entry_price) + (pos.quantity * pos.entry_price)
                existing.entry_price = new_cost / total_qty
                existing.quantity = total_qty
        else:
            self.positions[pos.symbol] = pos
            
    def to_dict(self):
        return asdict(self)
        
    @classmethod
    def from_dict(cls, data):
        positions = {}
        for sym, pos_data in data.get('positions', {}).items():
            # Filter out computed/injected fields that aren't in constructor
            # (they'll be recalculated)
            allowed_fields = {
                'symbol', 'quantity', 'entry_price', 'current_price', 'currency',
                'isin', 'entry_date', 'direction', 'stop_loss', 'initial_risk',
                'days_held', 'pos_pct', 'risk_pct', 'dist_pct', 'status_flags'
            }
            filtered = {k: v for k, v in pos_data.items() if k in allowed_fields}
            positions[sym] = Position(**filtered)
        
        return cls(
            timestamp=data['timestamp'],
            cash=data['cash'],
            equity=data['equity'],
            positions=positions
        )


@dataclass
class PortfolioSummary:
    """Aggregate portfolio metrics for dashboard display."""
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
