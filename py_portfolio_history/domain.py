from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import date, datetime

# --- Enums ---
class TransactionType(Enum):
    BUY = "Buy"
    SELL = "Sell"
    DEPOSIT = "Deposit"
    WITHDRAWAL = "Withdrawal"
    DIVIDEND = "Dividend"

# --- Domain Data Classes (Input) ---
@dataclass
class TradeEvent:
    id: str
    date: date
    time: str
    symbol: str
    isin: str
    type: TransactionType
    quantity: Decimal
    price: Decimal
    commission: Decimal
    currency: str

@dataclass
class CashEvent:
    id: str
    date: date
    type: TransactionType # DEPOSIT / WITHDRAWAL
    amount: Decimal
    currency: str

@dataclass
class DividendEvent:
    id: str
    date: date
    symbol: str
    isin: str
    amount: Decimal # Net amount typically
    currency: str

# --- Domain Data Classes (State & Output) ---

@dataclass
class OpenPosition:
    symbol: str
    isin: str
    quantity: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    accumulated_fees: Decimal
    currency: str
    exchange_rate: Decimal
    first_entry_date: date  # NEW: F-CALC-120
    holding_days: int       # NEW: F-CALC-120

@dataclass
class ClosedTrade:
    entry_id: str
    exit_id: str
    symbol: str
    quantity: Decimal
    entry_date: date
    exit_date: date
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    fees: Decimal
    real_pnl: Decimal
    holding_days: int
    winning_trade: bool

@dataclass
class PortfolioSnapshot:
    date: date
    cash_balance: Decimal
    invested_capital: Decimal
    market_value_positions: Decimal
    total_equity: Decimal # Cash + Market Value
    drawdown: Decimal
    open_positions: List[OpenPosition]
    performance: 'PerformanceMetrics' # NEW: F-CALC-010/020 (ICD-DAT-041)

@dataclass
class PnLBreakdown:
    """Three-tier PnL breakdown as per F-CALC-050"""
    trading_pnl: Decimal   # Pure price difference * quantity * exitFX
    real_pnl: Decimal      # Trading PnL - fees
    accounting_pnl: Decimal # Real PnL + FX gains/losses

@dataclass
class PerformanceMetrics:
    total_realized_pnl: Decimal
    total_fees: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    expectancy: Decimal
    pnl_breakdown: 'PnLBreakdown'  # NEW: F-CALC-050
    total_closed_trades: int       # NEW: F-CALC-130
    total_open_positions: int      # NEW: F-CALC-130
    total_transactions: int        # NEW: F-CALC-130

@dataclass
class EventSnapshot:
    """ Wraps a PortfolioSnapshot with Event Metadata for XML Output """
    event_id: str
    event_type: str        # BUY, SELL, DEPOSIT, DIVIDEND
    timestamp: datetime
    snapshot: PortfolioSnapshot
    # Event Specifics
    symbol: Optional[str] = None
    quantity: Optional[Decimal] = None
    market_value: Optional[Decimal] = None


# --- Interfaces ---

class IMarketDataProvider:
    def get_market_price(self, isin: str, ticker: str, query_date: date) -> Decimal:
        """ 
        Returns closing price for date. 
        MUST implement Lazy Fetching (call datafetcher.py if missing).
        Fallback to 0.0 or previous close if unavailable.
        """
        raise NotImplementedError

    def get_fx_rate(self, from_curr: str, to_curr: str, query_date: date) -> Decimal:
        """ Returns FX rate. Uses Lazy Fetching for pairs. """
        raise NotImplementedError

class IXmlParser:
    def parse_trades(self, filepath: str) -> List[TradeEvent]: raise NotImplementedError
    def parse_cash(self, filepath: str) -> List[CashEvent]: raise NotImplementedError
    def parse_dividends(self, filepath: str) -> List[DividendEvent]: raise NotImplementedError
