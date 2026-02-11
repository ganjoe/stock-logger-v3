"""
Risk Management Interfaces and DTOs.

Defines the abstract base class for risk strategies and the data transfer objects
used across all sizing implementations.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


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
    """The output of a position sizing calculation."""
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


class RiskStrategy(ABC):
    """Abstract base class for risk/sizing strategies."""

    @abstractmethod
    def calculate_wallet_context(self, equity: float, current_exposure: float,
                                  target_exposure_pct: float) -> SizingContext:
        """Calculate available budget based on target exposure."""
        pass

    @abstractmethod
    def calculate_sizing(self, context: SizingContext, params: TradeParameters) -> SizingResult:
        """Calculate position size recommendation."""
        pass
