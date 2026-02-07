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
        if currency == "EUR": return amount
        rate = self.market_data.get_fx_rate(currency, "EUR", query_date)
        return amount * rate

    def process_transaction(self, t: Transaction) -> PortfolioSnapshot:
        """
        Main entry point for any event. Dispatch based on type.
        """
        # We assume t.type is a string from parser constant
        t_type = t.type.upper()
        
        snap = None
        
        if t_type in ["BUY", "SELL"]:
            snap = self._process_trade(t)
        elif t_type in ["DEPOSIT", "WITHDRAWAL"]:
            snap = self._process_cash(t)
        elif t_type == "DIVIDEND":
            # XML Parser might call it DIVIDEND, but TransactionType enum might be different
            # We'll stick to string handling for safety as types.py uses strings
            snap = self._process_dividend(t)
        else:
            logging.warning(f"Unknown transaction type: {t_type}")
            snap = self._create_snapshot(t.date)
            
        return snap

    def _process_trade(self, t: Transaction) -> PortfolioSnapshot:
        self.transaction_count += 1
        date_obj = t.date.date()
        
        # 1. Update Cash (Immediate Fee impact + Principal)
        # Note: Fees are distinct. Principal is Price * Qty.
        # Fees are usually Commission field.
        
        total_value = t.price * t.quantity
        total_value_eur = self._convert_to_eur(total_value, t.currency, date_obj)
        fees_eur = self._convert_to_eur(t.commission, t.currency, date_obj)
        
        # Update Cumulative Fees
        self.cum_fees += fees_eur
        
        if t.type == "BUY":
            # Cash outflow: Principal + Fees
            self.cash_balance_eur -= (total_value_eur + fees_eur)
            
            # Add Position Logic
            self._handle_buy(t)
            
        elif t.type == "SELL":
            # Cash inflow: Principal - Fees
            self.cash_balance_eur += (total_value_eur - fees_eur)
            
            # Match Logic (LIFO)
            self._handle_sell_lifo(t)

        return self._create_snapshot(t.date)

    def _handle_buy(self, t: Transaction):
        symbol = t.symbol
        
        if symbol not in self.open_positions:
            self.open_positions[symbol] = Position(
                symbol=symbol,
                isin=t.isin,
                quantity=Decimal("0"),
                avg_entry_price=Decimal("0"),
                current_price=t.price,
                market_value=Decimal("0"),
                accumulated_fees=Decimal("0"),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                holding_days=0,
                currency=t.currency,
                exchange_rate=Decimal("1.0"),
                tranches=[]
            )
            
        pos = self.open_positions[symbol]
        
        # Add Tranche
        tranche = Tranche(
            id=t.id,
            date=t.date,
            quantity=t.quantity,
            price=t.price,
            commission=t.commission,
            isin=t.isin,
            currency=t.currency
        )
        pos.tranches.append(tranche)
        
        # Update Position Aggregates
        pos.quantity += t.quantity
        pos.accumulated_fees += t.commission
        
        # Weighted Average Entry Price update
        total_cost = sum(tr.quantity * tr.price for tr in pos.tranches)
        if pos.quantity > 0:
            pos.avg_entry_price = total_cost / pos.quantity

    def _handle_sell_lifo(self, t: Transaction):
        symbol = t.symbol
        remaining_qty = t.quantity
        
        if symbol not in self.open_positions:
            # Short Sell logic or Error?
            # Assuming Long Only for now, or just logging warning
            logging.warning(f"SELL without position for {symbol}. Ignoring matching logic.")
            return

        pos = self.open_positions[symbol]
        
        # LIFO Matching: Iterate from end
        # We use a while loop popping from end or index access
        
        generated_closed_trades = []
        
        while remaining_qty > 0 and pos.tranches:
            # Last In First Out
            tranche = pos.tranches[-1] # Peek last
            
            match_qty = min(remaining_qty, tranche.quantity)
            
            # Calculate PnL for this match
            # Fees Allocation: 
            # Buy Fee Portion = TrancheFee * (MatchQty / TrancheOriginalQty?) 
            # Problem: We modified Tranche Qty in place. We should track original qty or unit fee?
            # Simplification: Unit Fee = TrancheComm / TrancheQty
            unit_buy_fee = tranche.commission / tranche.quantity if tranche.quantity > 0 else 0
            buy_fee_part = unit_buy_fee * match_qty
            
            # Sell Fee Portion = SellComm * (MatchQty / TotalSellQty)
            sell_fee_part = t.commission * (match_qty / t.quantity) if t.quantity > 0 else 0
            
            gross_pnl = (t.price - tranche.price) * match_qty
            total_fees = buy_fee_part + sell_fee_part
            real_pnl = gross_pnl - total_fees
            
            # --- CURRENCY CONVERSION FOR PNL ---
            # PnL values are in trade currency. Need to convert to EUR for cumulative tracking?
            # Yes, standardizing on EUR for accounting.
            date_obj = t.date.date()
            gross_pnl_eur = self._convert_to_eur(gross_pnl, t.currency, date_obj)
            real_pnl_eur = self._convert_to_eur(real_pnl, t.currency, date_obj)
            
            # Update Cumulative Stats
            self.cum_trading_pnl += gross_pnl_eur
            self.cum_realized_pnl += real_pnl_eur
            # Accounting PnL = Real PnL (in EUR)
            self.cum_accounting_pnl += real_pnl_eur 
            
            # Create ClosedTrade Record
            closed = ClosedTrade(
                entry_id=tranche.id,
                exit_id=t.id,
                symbol=symbol,
                quantity=match_qty,
                entry_date=tranche.date,
                exit_date=t.date,
                entry_price=tranche.price,
                exit_price=t.price,
                gross_pnl=gross_pnl_eur, # Storing in EUR for consistency? Or Native?
                # Types.py doesn't specify currency. Let's start storing EUR to match aggregations.
                fees=self._convert_to_eur(total_fees, t.currency, date_obj),
                real_pnl=real_pnl_eur,
                holding_days=(t.date - tranche.date).days,
                winning_trade=(real_pnl > 0)
            )
            self.closed_trades.append(closed)
            
            # Update Tranche
            remaining_qty -= match_qty
            
            if match_qty == tranche.quantity:
                pos.accumulated_fees -= tranche.commission # Reduce total fees by the tranche's full fee
                pos.tranches.pop() # Remove fully closed tranche (LIFO pop is efficient)
            else:
                # Partial Close
                tranche.quantity -= match_qty
                tranche.commission -= buy_fee_part # Reduce remaining fee burden
                pos.accumulated_fees -= buy_fee_part # Update position total fees matches tranche reduction
        
        # After matching loop
        # Update Position Aggregates
        pos.quantity -= (t.quantity - remaining_qty)
        # Recalculate Avg Price
        if pos.quantity > 0:
             total_cost = sum(tr.quantity * tr.price for tr in pos.tranches)
             pos.avg_entry_price = total_cost / pos.quantity
        else:
            pos.avg_entry_price = Decimal("0")
            
        if pos.quantity == 0:
            del self.open_positions[symbol]

    def _process_cash(self, t: Transaction) -> PortfolioSnapshot:
        self.transaction_count += 1 # Is cash a transaction? "Transactions (Buy + Sell)" per requirement likely means Trades.
        # Req F-CALC-130: "Transactions (Anzahl aller Buy + Sell Transaktionen)."
        # So maybe NOT cash. But for now let's stick to strict interpretation: Buy+Sell.
        # Revert increment if strict. But harmless to track. Let's follow req STRICTLY: Buy+Sell only?
        # "Transactions (Anzahl aller Buy + Sell Transaktionen)" -> Yes.
        self.transaction_count -= 1 # Undo helper increment if strictly Buy/Sell
        
        amount_eur = self._convert_to_eur(t.quantity, t.currency, t.date.date()) 
        # Note: In cash events, quantity usually holds amount
        
        if t.type == "DEPOSIT":
            self.cash_balance_eur += amount_eur
            self.inflows_total += amount_eur
        elif t.type == "WITHDRAWAL":
            self.cash_balance_eur -= amount_eur # Amount is usually positive in XML, logic subtracts
            # Withdrawals reduce Inflows? Or are Flows = In - Out?
            # Usually Net Flow.
            self.inflows_total -= amount_eur
            
        return self._create_snapshot(t.date)

    def _process_dividend(self, t: Transaction) -> PortfolioSnapshot:
        # F-LOGIC-026: Dividends treat as Inflows
        # Dividends are income.
        amount_eur = self._convert_to_eur(t.quantity, t.currency, t.date.date()) # Div amount in qty? Or Price?
        # Usually Div event has amount. Mapping to Transaction struct: quantity = amount?
        
        self.cash_balance_eur += amount_eur
        self.inflows_total += amount_eur 
        
        # Update Accounting PnL (Divs are profit)
        self.cum_accounting_pnl += amount_eur
        
        return self._create_snapshot(t.date)

    def _create_snapshot(self, timestamp: datetime) -> PortfolioSnapshot:
        date_obj = timestamp.date()
        
        # Calculate Market Value of Open Positions
        total_market_value = Decimal("0")
        
        for symbol, pos in self.open_positions.items():
            # Get Price
            price = self.market_data.get_market_price(pos.isin, symbol, date_obj)
            fx_rate = self.market_data.get_fx_rate(pos.currency, "EUR", date_obj)
            
            price_eur = price * fx_rate
            mv_eur = pos.quantity * price_eur
            
            pos.current_price = price
            pos.market_value = mv_eur
            pos.exchange_rate = fx_rate
            
            # Calc Unrealized PnL (Market Value - Cost Basis)
            # Cost Basis = Sum(Tranche.Qty * Tranche.Price) converted to EUR using CURRENT rate or HISTORICAL?
            # Unrealized is usually: (CurrentPrice - AvgEntry) * Qty * CurrentFX
            cost_basis_eur = pos.avg_entry_price * pos.quantity * fx_rate 
            pos.unrealized_pnl = mv_eur - cost_basis_eur
            
            # Holding Days (First Entry) - F-CALC-120
            if pos.tranches:
                first_date = min(tr.date for tr in pos.tranches)
                pos.holding_days = (timestamp - first_date).days
            
            total_market_value += mv_eur
            
        # Invested = Market Value (F-CALC-070 New Def: Exposure)
        invested = total_market_value 
        
        total_equity = self.cash_balance_eur + total_market_value
        
        # HWM
        adj_equity = total_equity - self.inflows_total
        if adj_equity > self.high_water_mark:
            self.high_water_mark = adj_equity
            
        dd = Decimal("0")
        if self.high_water_mark > 0:
             dd = (self.high_water_mark - adj_equity) / self.high_water_mark * 100
             
        # Metrics Construction
        # F-CALC-130: Stats
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
        
        # Clone positions for snapshot (shallow copy of dict values ok since we replace objects on update?)
        # Better deep copy strictly, but let's assume one snapshot per event sequence.
        # To be safe, we create a dict copy.
        import copy
        pos_snapshot = copy.deepcopy(self.open_positions)

        return PortfolioSnapshot(
            date=timestamp,
            cash=self.cash_balance_eur,
            invested=invested,
            market_value_total=total_market_value,
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
        # Formula: (WinRate * AvgWin) - (LossRate * AvgLoss)
        wins = [t.gross_pnl for t in self.closed_trades if t.gross_pnl > 0]
        losses = [abs(t.gross_pnl) for t in self.closed_trades if t.gross_pnl <= 0]
        
        avg_win = float(sum(wins) / len(wins)) if wins else 0.0
        avg_loss = float(sum(losses) / len(losses)) if losses else 0.0
        win_rate = len(wins) / len(self.closed_trades)
        
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
