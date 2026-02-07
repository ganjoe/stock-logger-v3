from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import logging

# Use new types
from .types import (
    Transaction, Position, Tranche, ClosedTrade, 
    PerformanceMetrics, PortfolioSnapshot
)

# We still need the MarketData interface
# Assuming it hasn't changed location, usually defined in market_data.py or similar
# For type hinting, we can import or define Protocol
from typing import Protocol

class IMarketDataProvider(Protocol):
    def get_market_price(self, isin: str, symbol: str, date_obj: date) -> Decimal: ...
    def get_fx_rate(self, from_curr: str, to_curr: str, date_obj: date) -> Decimal: ...


class PortfolioCalculator:
    def __init__(self, market_data: IMarketDataProvider):
        self.market_data = market_data
        
        # State
        self.cash_balance_eur: Decimal = Decimal("0")
        self.collateral_balance_eur: Decimal = Decimal("0") # Short Sale Proceeds
        self.inflows_total: Decimal = Decimal("0") # Deposits + Dividends (F-LOGIC-026)
        
        # Positions State: Symbol -> Position Object
        self.open_positions: Dict[str, Position] = {}
        
        # History
        self.closed_trades: List[ClosedTrade] = []
        self.snapshots: List[PortfolioSnapshot] = []
        
        # Cumulative Metrics (F-CALC-140)
        self.cum_trading_pnl: Decimal = Decimal("0")
        self.cum_realized_pnl: Decimal = Decimal("0") # Trading - Fees
        self.cum_accounting_pnl: Decimal = Decimal("0") # Real + FX (for divs etc)
        self.cum_fees: Decimal = Decimal("0")
        
        self.transaction_count: int = 0
        
        # High Water Mark for Drawdown
        self.high_water_mark: Decimal = Decimal("0")

    def _convert_to_eur(self, amount: Decimal, currency: str, query_date: date) -> Decimal:
        # User Requirement: Ignore FX conversions. Treat all amounts as 1:1.
        return amount
        # if currency == "EUR": return amount
        # rate = self.market_data.get_fx_rate(currency, "EUR", query_date)
        # return amount * rate

    def process_transaction(self, t: Transaction) -> PortfolioSnapshot:
        """
        Main entry point for any event. Dispatch based on type.
        """
        t_type = t.type.upper()
        
        snap = None
        
        if t_type in ["BUY", "SELL"]:
            snap = self._process_trade(t)
        elif t_type in ["DEPOSIT", "WITHDRAWAL"]:
            snap = self._process_cash(t)
        elif t_type == "DIVIDEND":
            # Treat as dividend
            snap = self._process_dividend(t)
        else:
            logging.warning(f"Unknown transaction type: {t_type}")
            snap = self._create_snapshot(t.date)
            
        return snap

    def _process_trade(self, t: Transaction) -> PortfolioSnapshot:
        self.transaction_count += 1
        
        # Cash Update Update:
        # We delegrate Cash/Collateral updates to the Position Logic (Init/Add/Reduce)
        # to correctly handle Short Proceeds vs Free Cash.
        
        fees = t.commission
        self.cum_fees += fees
        
        # Position Logic (Long/Short/Flip)
        self._update_position_logic(t)
        
        return self._create_snapshot(t.date)

    def _update_position_logic(self, t: Transaction):
        symbol = t.symbol
        side = 1 if t.type == "BUY" else -1
        qty_remaining = t.quantity
        
        # Ensure position exists via Init if needed
        if symbol not in self.open_positions:
             self._init_position(t, side, qty_remaining)
             return
             
        pos = self.open_positions[symbol]
        pos_side = 1 if pos.quantity >= 0 else -1
        
        # Verify valid existing position state
        if pos.quantity == 0: pos_side = side 
        
        if side == pos_side:
            # Same direction: Adding to position
            self._add_tranche(pos, t, side, qty_remaining)
        else:
            # Opposite direction: Reducing or Flipping
            self._reduce_position(pos, t, side, qty_remaining)

    def _init_position(self, t: Transaction, side: int, qty: Decimal):
        val = qty * t.price
        fees = t.commission
        
        # Cash/Collateral Logic
        if side == -1: # Opening Short
            self.collateral_balance_eur += val
            self.cash_balance_eur -= fees
        else: # Opening Long
            self.cash_balance_eur -= (val + fees)

        s_qty = qty * side
        pos = Position(
            symbol=t.symbol,
            isin=t.isin,
            quantity=s_qty,
            avg_entry_price=t.price,
            current_price=t.price,
            market_value=Decimal("0"), # Calculated in snapshot
            accumulated_fees=t.commission,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            holding_days=0,
            currency=t.currency,
            exchange_rate=Decimal("1.0"),
            tranches=[]
        )
        self.open_positions[t.symbol] = pos
        # Add Tranche (Tranche quantity usually absolute)
        # We assume Tranche Qty is ABSOLUTE exposure. Position Sign determines direction.
        tr = Tranche(t.id, t.date, qty, t.price, t.commission, t.isin, t.currency)
        pos.tranches.append(tr)

    def _add_tranche(self, pos: Position, t: Transaction, side: int, qty: Decimal):
        # Cash/Collateral Logic
        val = qty * t.price
        fees = t.commission
        if side == -1: # Increasing Short
            self.collateral_balance_eur += val
            self.cash_balance_eur -= fees
        else: # Increasing Long
             self.cash_balance_eur -= (val + fees)

        # Update Pos
        pos.quantity += (qty * side)
        pos.accumulated_fees += t.commission
        
        # Tranche
        tr = Tranche(t.id, t.date, qty, t.price, t.commission, t.isin, t.currency)
        pos.tranches.append(tr)
        
        # Recalc Avg Price
        self._recalc_avg_price(pos)

    def _reduce_position(self, pos: Position, t: Transaction, side: int, qty: Decimal):
        qty_to_process = qty
        
        # Identify Position Direction: 1 (Long) or -1 (Short)
        pos_side = 1 if pos.quantity > 0 else -1
        
        while qty_to_process > 0 and pos.tranches:
            tranche = pos.tranches[-1] # LIFO
            match_qty = min(qty_to_process, tranche.quantity)
            
            # PnL Calculation
            # Long Closing (Sell, Side -1): Profit if Price > Entry. (Price - Entry) * match_qty.
            # Short Closing (Buy, Side 1): Profit if Entry > Price. (Entry - Price) * match_qty.
            # Combined Formula: (t.price - tranche.price) * pos_side * match_qty
            
            gross_pnl = (t.price - tranche.price) * match_qty * pos_side
            
            # Proportional Fees
            buy_fee = (tranche.commission / tranche.quantity) * match_qty if tranche.quantity > 0 else 0
            sell_fee = (t.commission / t.quantity) * match_qty if t.quantity > 0 else 0
            total_fees = buy_fee + sell_fee
            
            real_pnl = gross_pnl - total_fees
            
            # Cash/Collateral Logic for this chunk
            # Current (Closing) Fee Portion:
            closing_fee_part = sell_fee # The fee from 't' (the closer)
            
            self.cash_balance_eur -= closing_fee_part
            
            if pos_side == 1:
                # Closing Long (Sell)
                proceeds = t.price * match_qty
                self.cash_balance_eur += proceeds
            else:
                # Closing Short (Buy/Cover)
                cost = t.price * match_qty
                collateral_release = tranche.price * match_qty
                
                self.collateral_balance_eur -= collateral_release
                # Net Cash Flow = Collateral Releaase - Cost (to buy back)
                self.cash_balance_eur += (collateral_release - cost)
            
            # Metrics (Ignore FX)
            self.cum_trading_pnl += gross_pnl
            self.cum_realized_pnl += real_pnl
            self.cum_accounting_pnl += real_pnl
            
            # Create Closed Trade
            # For Short: Entry = Tranche (Sell), Exit = t (Buy).
            # For Long: Entry = Tranche (Buy), Exit = t (Sell).
            closed = ClosedTrade(
                entry_id=tranche.id, exit_id=t.id, symbol=pos.symbol, quantity=match_qty,
                entry_date=tranche.date, exit_date=t.date,
                entry_price=tranche.price, exit_price=t.price,
                gross_pnl=gross_pnl, fees=total_fees, real_pnl=real_pnl,
                holding_days=(t.date - tranche.date).days,
                winning_trade=(real_pnl > 0)
            )
            self.closed_trades.append(closed)
            
            # Update Tranche
            if match_qty == tranche.quantity:
                # Fully closed tranche
                pos.accumulated_fees -= tranche.commission
                pos.tranches.pop()
            else:
                # Partial close
                tranche.quantity -= match_qty
                tranche.commission -= buy_fee
                pos.accumulated_fees -= buy_fee
                
            qty_to_process -= match_qty
            pos.quantity -= (match_qty * pos_side) # Reduce magnitude
            
        self._recalc_avg_price(pos)
        
        # Cleanup Empty Position
        if pos.quantity == 0 and not pos.tranches:
             if pos.symbol in self.open_positions:
                del self.open_positions[pos.symbol]
        
        # FLIP Logic: If quantity still remains, open new position in opposite direction
        if qty_to_process > 0:
            # Check if cleaned up
            pass # Already deleted above if 0.
            
            # Trigger Init for remainder
            self._init_position(t, side, qty_to_process)

    def _recalc_avg_price(self, pos: Position):
        if not pos.tranches: 
            pos.avg_entry_price = Decimal("0")
            return
        total_cost = sum(tr.quantity * tr.price for tr in pos.tranches)
        total_qty = sum(tr.quantity for tr in pos.tranches)
        if total_qty > 0:
            pos.avg_entry_price = total_cost / total_qty

    def _process_cash(self, t: Transaction) -> PortfolioSnapshot:
        # F-CALC-130: Transactions count Buy+Sell only.
        # Strict adherence -> do not increment here.
        
        amount = t.quantity # Absolute
        
        if t.type == "DEPOSIT":
            self.cash_balance_eur += amount
            self.inflows_total += amount
        elif t.type == "WITHDRAWAL":
            self.cash_balance_eur -= amount
            self.inflows_total -= amount
            
        return self._create_snapshot(t.date)

    def _process_dividend(self, t: Transaction) -> PortfolioSnapshot:
        # F-LOGIC-026: Dividends = Inflow + Profit
        amount = t.quantity
        
        self.cash_balance_eur += amount
        self.inflows_total += amount
        self.cum_accounting_pnl += amount
        
        return self._create_snapshot(t.date)

    def _create_snapshot(self, timestamp: datetime) -> PortfolioSnapshot:
        total_market_value_signed = Decimal("0")
        total_exposure = Decimal("0")
        
        for symbol, pos in self.open_positions.items():
            # Price: Use avg_entry_price from transaction data (broker CSV)
            # No market data lookup - transaction price is the single source of truth
            price = pos.avg_entry_price
            
            # Market Value (Signed)
            # Long: positive. Short: negative.
            mv = pos.quantity * price
            
            # Exposure (Absolute)
            exposure = abs(mv)
            
            pos.current_price = price
            pos.market_value = mv
            pos.exchange_rate = Decimal("1.0")
            
            # Unrealized PnL: Always 0 when using entry price
            # (Current = Entry, so no unrealized gain/loss)
            pos.unrealized_pnl = Decimal("0")
            
            if pos.tranches:
                first_date = min(tr.date for tr in pos.tranches)
                pos.holding_days = (timestamp - first_date).days
            
            total_market_value_signed += mv
            total_exposure += exposure
            
        # Calc Equity
        # Equity = Cash + Collateral + Signed Market Value
        total_equity = self.cash_balance_eur + self.collateral_balance_eur + total_market_value_signed
        
        # HWM Logic
        adj_equity = total_equity - self.inflows_total
        if adj_equity > self.high_water_mark:
            self.high_water_mark = adj_equity
            
        dd = Decimal("0")
        if self.high_water_mark > 0:
             dd = (self.high_water_mark - adj_equity) / self.high_water_mark * 100
             
        # Metrics
        closed_count = len(self.closed_trades)
        open_count = len(self.open_positions)
        
        metrics = PerformanceMetrics(
            trading_pnl=self.cum_trading_pnl,
            realized_pnl=self.cum_realized_pnl,
            accounting_pnl=self.cum_accounting_pnl,
            fees_total=self.cum_fees,
            inflows_total=self.inflows_total,
            win_rate=self._calc_win_rate(),
            profit_factor=self._calc_profit_factor(),
            expectancy=self._calc_expectancy(),
            closed_trades_count=closed_count,
            open_positions_count=open_count,
            total_transactions_count=self.transaction_count
        )
        
        import copy
        pos_snapshot = copy.deepcopy(self.open_positions)

        return PortfolioSnapshot(
            date=timestamp,
            cash=self.cash_balance_eur,
            collateral=self.collateral_balance_eur,
            invested=total_exposure, # Use Exposure for Invested field
            market_value_total=total_market_value_signed,
            total_equity=total_equity,
            inflows=self.inflows_total,
            drawdown=dd,
            performance=metrics,
            positions=pos_snapshot
        )

    def _calc_win_rate(self) -> float:
        if not self.closed_trades: return 0.0
        wins = sum(1 for t in self.closed_trades if t.winning_trade)
        return (wins / len(self.closed_trades)) * 100

    def _calc_profit_factor(self) -> float:
        gross_wins = sum(t.gross_pnl for t in self.closed_trades if t.gross_pnl > 0)
        gross_losses = abs(sum(t.gross_pnl for t in self.closed_trades if t.gross_pnl <= 0))
        if gross_losses == 0: return 999.0 if gross_wins > 0 else 0.0
        return float(gross_wins / gross_losses)

    def _calc_expectancy(self) -> float:
        if not self.closed_trades: return 0.0
        wins = [t.gross_pnl for t in self.closed_trades if t.gross_pnl > 0]
        losses = [abs(t.gross_pnl) for t in self.closed_trades if t.gross_pnl <= 0]
        
        avg_win = float(sum(wins) / len(wins)) if wins else 0.0
        avg_loss = float(sum(losses) / len(losses)) if losses else 0.0
        win_rate = len(wins) / len(self.closed_trades)
        
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
