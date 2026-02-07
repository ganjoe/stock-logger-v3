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
class Tranche:
    id: str  # Original trade ID
    date: datetime
    quantity: Decimal
    price: Decimal
    commission: Decimal # Remaining commission portion
    isin: str
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
    realized_pnl: Decimal # Realized PnL from closed tranches (if any logic needs this, mainly for closed trades)
    # Actually realize_pnl usually belongs to ClosedTrade, not Position (which is open)
    # But F-CALC-070/042 asks for "Performance" inside Position? 
    # ICD-DAT-042: <Performance><Trading>...</Performance> inside Position.
    # This usually means "Unrealized" PnL for the open position.
    unrealized_pnl: Decimal 
    holding_days: int
    currency: str
    exchange_rate: Decimal
    
    # Tranches for matching
    tranches: List[Tranche] = field(default_factory=list)

@dataclass
class ClosedTrade:
    entry_id: str
    exit_id: str
    symbol: str
    quantity: Decimal
    entry_date: datetime
    exit_date: datetime
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    fees: Decimal
    real_pnl: Decimal
    holding_days: int
    winning_trade: bool

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
    collateral: Decimal
    invested: Decimal # Market Value Exposure
    market_value_total: Decimal
    total_equity: Decimal
    inflows: Decimal
    drawdown: Decimal
    performance: PerformanceMetrics
    positions: Dict[str, Position]

@dataclass
class EventWithSnapshot:
    transaction: Transaction
    snapshot: PortfolioSnapshot
