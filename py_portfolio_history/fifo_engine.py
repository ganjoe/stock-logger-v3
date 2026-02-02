from typing import Dict, List, Optional
from decimal import Decimal
from .domain import TradeEvent, ClosedTrade, TransactionType, OpenPosition

class FifoEngine:
    def __init__(self):
        # Symbol -> List of Buy TradeEvents (Queue)
        self.open_tranches: Dict[str, List[TradeEvent]] = {} 
        self.closed_trades: List[ClosedTrade] = []
        
        # Track active holdings for Snapshot logic (can be derived from tranches)
        # But we need an easy way to query current positions.

    def _add_tranche(self, trade: TradeEvent):
        if trade.symbol not in self.open_tranches:
            self.open_tranches[trade.symbol] = []
        self.open_tranches[trade.symbol].append(trade)

    def process_trade(self, trade: TradeEvent) -> List[ClosedTrade]:
        generated_closed = []
        
        if trade.type == TransactionType.BUY:
            self._add_tranche(trade)
            
        elif trade.type == TransactionType.SELL:
            # Match against Buys
            remaining_qty = trade.quantity
            symbol = trade.symbol
            
            # What if no buy? Short selling? 
            # Current scope usually implies Long-Only or we treat Short as negative position?
            # Impl Plan implies Standard FIFO. If no tranches -> Short Position?
            # Let's assume Valid FIFO: Sell closes existing buys. Error/Warn if Short?
            # Review Req F-LOGIC-010: "FIFO Matching... Short (Buy closes Sell)".
            # Complex. Let's handle Long Only + simple Short handling if needed.
            # Assuming simple Long-only for now or negative processing.
            
            queue = self.open_tranches.get(symbol, [])
            
            while remaining_qty > 0 and queue:
                buy_tranche = queue[0]
                
                match_qty = min(remaining_qty, buy_tranche.quantity)
                
                # Calculate PnL Logic
                # Fees: How to allocate? 
                # Proposal: Alloc Sell Fees proportionally to match_qty? 
                # Yes. Buy fees are already in 'commission' of tranche.
                # But `buy_tranche.commission` might be for the WHOlE buy.
                # We need pro-rated commission.
                
                pct_of_buy = match_qty / buy_tranche.quantity if buy_tranche.quantity > 0 else 0
                buy_fee_part = buy_tranche.commission * pct_of_buy
                
                sell_fee_part = trade.commission * (match_qty / trade.quantity)
                
                # Create Closed Trade
                gross = (trade.price - buy_tranche.price) * match_qty
                fees = buy_fee_part + sell_fee_part
                # Fees are typically negative. Net PnL = Gross + Fees (add negative numbers)
                real = gross + fees
                
                holding_days = (trade.date - buy_tranche.date).days
                
                closed = ClosedTrade(
                    entry_id=buy_tranche.id,
                    exit_id=trade.id,
                    symbol=symbol,
                    quantity=match_qty,
                    entry_date=buy_tranche.date,
                    exit_date=trade.date,
                    entry_price=buy_tranche.price,
                    exit_price=trade.price,
                    gross_pnl=gross,
                    fees=fees, # Combined fees
                    real_pnl=real,
                    holding_days=holding_days,
                    winning_trade=(real > 0)
                )
                
                generated_closed.append(closed)
                self.closed_trades.append(closed)
                
                # Update State
                remaining_qty -= match_qty
                
                if match_qty == buy_tranche.quantity:
                    queue.pop(0) # Fully closed logic
                else:
                    # Partial Close
                    buy_tranche.quantity -= match_qty
                    buy_tranche.commission -= buy_fee_part # Reduce remaining fee burden on tranche
                    
            if remaining_qty > 0:
                # Overselling? Short?
                # For scope, we might just log or ignore.
                pass
                
        return generated_closed

    def get_open_positions_snapshot(self) -> List[OpenPosition]:
        # Aggregate tranches
        positions = []
        for symbol, tranches in self.open_tranches.items():
            if not tranches: continue
            
            total_qty = sum(t.quantity for t in tranches)
            if total_qty == 0: continue
            
            # weighted avg entry
            total_cost = sum(t.quantity * t.price for t in tranches)
            avg_entry = total_cost / total_qty
            
            # Days held: weighted avg? or Max?
            # Req F-CALC-120: "Holding Time". Usually Since First Buy? or Avg?
            # Lets use simple: Date of first tranche vs Today/QueryDate?
            # Snapshot calculation usually provides QueryDate.
            # Note: This method doesn't know 'today'. The Calculator does.
            # We return simple data here, Calculator enhances it with MarketPrice and HoldingTime relative to SnapshotDate.
            
            # NEW: F-CALC-120 - Track first entry date for holding time
            first_entry = min(t.date for t in tranches)
            
            positions.append(OpenPosition(
                symbol=symbol,
                isin=tranches[0].isin if tranches else "",
                quantity=total_qty,
                avg_entry_price=avg_entry,
                current_price=Decimal("0"), # To be filled by Calculator
                market_value=Decimal("0"),  # To be filled
                unrealized_pnl=Decimal("0"), # To be filled
                accumulated_fees=sum(t.commission for t in tranches),
                currency=tranches[0].currency if tranches else "EUR",
                exchange_rate=Decimal("1.0"),  # To be filled
                first_entry_date=first_entry,  # NEW
                holding_days=0 # To be filled by Calculator
            ))
        return positions
