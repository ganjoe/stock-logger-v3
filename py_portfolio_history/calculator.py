from typing import List, Dict, Any
from decimal import Decimal
from datetime import date, datetime
from .domain import (
    PortfolioSnapshot, OpenPosition, PerformanceMetrics, 
    IMarketDataProvider, TradeEvent, CashEvent, DividendEvent, 
    TransactionType, ClosedTrade, EventSnapshot
)
from .fifo_engine import FifoEngine

class PortfolioCalculator:
    def __init__(self, market_data: IMarketDataProvider):
        self.market_data = market_data
        
        self.cash_balance_eur: Decimal = Decimal("0")
        self.total_deposits_eur: Decimal = Decimal("0") # For Adj. Equity
        self.snapshots: List[PortfolioSnapshot] = []
        
        # Track Max Equity (HWM) for Drawdown
        self.high_water_mark: Decimal = Decimal("0")
        
        # NEW: F-CALC-130 - Track total transactions
        self.transaction_count: int = 0

    def _convert_to_eur(self, amount: Decimal, currency: str, query_date: date) -> Decimal:
        if currency == "EUR": return amount
        rate = self.market_data.get_fx_rate(currency, "EUR", query_date)
        return amount * rate

    def _create_snapshot(self, date_obj: date, event_info: str = "") -> PortfolioSnapshot:
        """ Helper to build current state snapshot """
        # Valuation of Open Positions
        # Note: We rely on FifoEngine having updated the positions state externally (or we pass it?)
        # Wait, FifoEngine state is external. We assume FifoEngine is up to date.
        # But we need access to fifo engine instance? 
        # The previous 'process_day' took 'fifo' as arg.
        # We need to pass fifo to the create_snapshot or store it?
        # Better: Pass 'fifo' to the process_* methods.
        raise NotImplementedError("This helper assumes internal access to open positions, but fifo is external.")

    def process_trade(self, t: TradeEvent, fifo: FifoEngine) -> EventSnapshot:
        date_obj = t.date
        
        # 1. Update Cash
        value_local = t.price * t.quantity
        value_eur = self._convert_to_eur(value_local, t.currency, date_obj)
        comm_eur = self._convert_to_eur(t.commission, t.currency, date_obj)
        
        if t.type == TransactionType.BUY:
            self.cash_balance_eur -= (value_eur + comm_eur)
        elif t.type == TransactionType.SELL:
            self.cash_balance_eur += (value_eur - comm_eur)
        
        # NEW: F-CALC-130 - Track transactions
        self.transaction_count += 1
            
        # 2. Snapshot
        snap = self._make_snapshot(date_obj, fifo)
        
        # 3. Wrap
        return EventSnapshot(
            event_id=t.id,
            event_type=t.type.name, # Enum name
            timestamp=datetime.combine(t.date, datetime.strptime(t.time, "%H:%M:%S").time()),
            snapshot=snap,
            symbol=t.symbol,
            quantity=t.quantity,
            market_value=value_local # In original currency as per ICD example? Or EUR? ICD ex shows 150.00 for stock price?
            # ICD Example: MarketValue <Value>150.00</Value> matches price usually? 
            # Or is it total value? ICD says "MarketValue" -> Value. 
            # Let's put total value of trade here.
        )

    def process_cash(self, c: CashEvent, fifo: FifoEngine) -> EventSnapshot:
        date_obj = c.date
        amount_eur = self._convert_to_eur(c.amount, c.currency, date_obj)
        
        if c.type == TransactionType.DEPOSIT:
            self.cash_balance_eur += amount_eur
            self.total_deposits_eur += amount_eur
        elif c.type == TransactionType.WITHDRAWAL:
            self.cash_balance_eur -= amount_eur
            self.total_deposits_eur -= amount_eur
            
        snap = self._make_snapshot(date_obj, fifo)
        
        return EventSnapshot(
            event_id=c.id,
            event_type="INFLOW" if c.type == TransactionType.DEPOSIT else "OUTFLOW",
            timestamp=datetime.combine(c.date, datetime.min.time()), # No time for cash usually
            snapshot=snap,
            market_value=c.amount # logic?
        )

    def process_dividend(self, d: DividendEvent, fifo: FifoEngine) -> EventSnapshot:
        date_obj = d.date
        amount_eur = self._convert_to_eur(d.amount, d.currency, date_obj)
        self.cash_balance_eur += amount_eur
        
        snap = self._make_snapshot(date_obj, fifo)
        
        return EventSnapshot(
            event_id=d.id,
            event_type="DIVIDEND",
            timestamp=datetime.combine(d.date, datetime.min.time()),
            snapshot=snap,
            symbol=d.symbol,
            market_value=d.amount
        )

    def _make_snapshot(self, date_obj: date, fifo: FifoEngine) -> PortfolioSnapshot:
        raw_positions = fifo.get_open_positions_snapshot()
        valued_positions = []
        total_market_value = Decimal("0")
        
        for p in raw_positions:
            curr_price = self.market_data.get_market_price(p.isin, p.symbol, date_obj)
            
            # Simple currency handling (same as before)
            asset_currency = "EUR"
            if p.isin.startswith("US"): asset_currency = "USD"
            
            price_eur = self._convert_to_eur(curr_price, asset_currency, date_obj)
            mv = price_eur * p.quantity
            cost_basis = p.avg_entry_price * p.quantity
            
            p.current_price = curr_price
            p.market_value = mv
            p.unrealized_pnl = mv - (cost_basis * (price_eur/curr_price if curr_price>0 else 1)) # Rough
            # NEW: F-CALC-120 - Calculate holding time from first entry
            p.holding_days = (date_obj - p.first_entry_date).days 
            
            valued_positions.append(p)
            total_market_value += mv
            
        total_equity = self.cash_balance_eur + total_market_value
        
        # High Water Mark Logic
        adjusted_equity = total_equity - self.total_deposits_eur
        if adjusted_equity > self.high_water_mark:
            self.high_water_mark = adjusted_equity
            
        dd = Decimal("0")
        if self.high_water_mark > 0:
            diff = self.high_water_mark - adjusted_equity
            dd = (diff / self.high_water_mark) * 100

        # Metrics
        metrics = self.calculate_metrics(fifo.closed_trades, fifo)

        return PortfolioSnapshot(
            date=date_obj,
            cash_balance=self.cash_balance_eur,
            invested_capital=total_market_value,
            market_value_positions=total_market_value,
            total_equity=total_equity,
            drawdown=dd,
            open_positions=valued_positions,
            performance=metrics
        )

    def calculate_metrics(self, closed_trades: List[ClosedTrade], fifo: FifoEngine) -> PerformanceMetrics:
        from .domain import PnLBreakdown
        
        if not closed_trades:
            return PerformanceMetrics(
                total_realized_pnl=Decimal(0),
                total_fees=Decimal(0),
                win_rate=Decimal(0),
                profit_factor=Decimal(0),
                max_drawdown=Decimal(0),
                expectancy=Decimal(0),
                pnl_breakdown=PnLBreakdown(
                    trading_pnl=Decimal(0),
                    real_pnl=Decimal(0),
                    accounting_pnl=Decimal(0)
                ),
                total_closed_trades=0,
                total_open_positions=0,
                total_transactions=self.transaction_count
            )
            
        total_pnl = sum(t.real_pnl for t in closed_trades)
        total_fees = sum(t.fees for t in closed_trades)
        
        # NEW: F-CALC-050 - Calculate 3-tier PnL
        # Trading PnL = gross_pnl (already calculated in ClosedTrade)
        trading_pnl_total = sum(t.gross_pnl for t in closed_trades)
        # Real PnL = Trading - Fees
        real_pnl_total = sum(t.real_pnl for t in closed_trades)
        # Accounting PnL = Real PnL (FX gains already included in conversions)
        accounting_pnl_total = real_pnl_total  # Currently same as real
        
        wins = [t for t in closed_trades if t.gross_pnl > 0]
        losses = [t for t in closed_trades if t.gross_pnl <= 0]
        
        win_rate = Decimal(len(wins)) / Decimal(len(closed_trades)) * 100
        
        gross_win = sum(t.gross_pnl for t in wins)
        gross_loss = abs(sum(t.gross_pnl for t in losses))
        
        profit_factor = gross_win / gross_loss if gross_loss > 0 else Decimal("999") # Inf
        
        # Max Drawdown from snapshots
        max_dd = max(s.drawdown for s in self.snapshots) if self.snapshots else Decimal("0")
        
        # Expectancy based on Trading PnL (F-CALC-100/ICD-CALC-020)
        avg_win = gross_win / len(wins) if wins else Decimal(0)
        avg_loss = gross_loss / len(losses) if losses else Decimal(0)
        # (WinRate% * AvgWin) - (LossRate% * AvgLoss) -> Normalized to 1.0 rate
        rate_dec = win_rate / 100
        expectancy = (rate_dec * avg_win) - ((1 - rate_dec) * avg_loss)
        
        # NEW: F-CALC-130 - Trade statistics
        open_pos_count = len(fifo.get_open_positions_snapshot())
        
        return PerformanceMetrics(
            total_realized_pnl=total_pnl,
            total_fees=total_fees,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            expectancy=expectancy,
            pnl_breakdown=PnLBreakdown(
                trading_pnl=trading_pnl_total,
                real_pnl=real_pnl_total,
                accounting_pnl=accounting_pnl_total
            ),
            total_closed_trades=len(closed_trades),
            total_open_positions=open_pos_count,
            total_transactions=self.transaction_count
        )
