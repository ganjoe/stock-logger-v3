
from decimal import Decimal
from typing import List, Tuple, Any
from alm_types import RawEvent, ProcessedEvent, PortfolioState, TransactionType, TradeMatch, MarketDataProvider

class TradeProcessor:
    def __init__(self, market_data: MarketDataProvider):
        self.market_data = market_data
        self.state = PortfolioState()

    def process_event(self, raw: RawEvent) -> ProcessedEvent:
        """
        Main entry point. Delegates to _process_trade or _process_transfer.
        Updates self.state.
        """
        if raw.type in (TransactionType.BUY, TransactionType.SELL):
            return self._process_trade(raw)
        elif raw.type == TransactionType.DIVIDEND:
            return self._process_dividend(raw)
        else:
            return self._process_transfer(raw)

    def _process_dividend(self, raw: RawEvent) -> ProcessedEvent:
        """ Handles Dividends. """
        processed = ProcessedEvent(
            event_id=raw.event_id,
            date=raw.timestamp,
            type=raw.type,
            symbol=raw.symbol,
            equity_change=raw.amount # Dividend increases equity
        )
        
        # Dividends do NOT affect Trading PnL, but affect Total Equity
        self.state.total_equity += raw.amount
        # Note: Dividend is NOT Inflow (external cash), it's internal gain
        
        self._update_metrics(processed)
        return processed

    def _process_trade(self, raw: RawEvent) -> ProcessedEvent:
        """ Handles Buy/Sell/Short/Cover logic with FIFO. """
        
        # 1. Get FX Rate (Format: USDEUR if Currency is USD)
        # Assuming Data is BASE=Currency, QUOTE=EUR.
        curr_pair = f"{raw.currency}EUR"
        date_str = raw.timestamp.strftime("%Y-%m-%d")
        fx_rate = self.market_data.get_fx_rate(curr_pair, date_str)
        
        # Determine if Opening or Closing first to init prices correctly
        symbol = raw.symbol
        if symbol not in self.state.open_positions:
            self.state.open_positions[symbol] = []
        open_positions = self.state.open_positions[symbol]
        
        is_closing = False
        if open_positions:
            first_qty = open_positions[0]['qty']
            if (raw.quantity > 0 and first_qty < 0) or (raw.quantity < 0 and first_qty > 0):
                is_closing = True
        
        # Init processed event.
        # If OPENING: EntryPrice = Raw.Price, ExitPrice = 0.
        # If CLOSING: EntryPrice = TBD (Avg), ExitPrice = Raw.Price.
        
        entry_p = Decimal("0")
        exit_p = Decimal("0")
        
        if not is_closing:
            entry_p = raw.price
            exit_p = Decimal("0") # or Raw.Price? Usually 0 if open.
        else:
            exit_p = raw.price
            # entry_p will be calculated later
        
        processed = ProcessedEvent(
            event_id=raw.event_id,
            date=raw.timestamp,
            type=raw.type,
            symbol=raw.symbol,
            quantity=raw.quantity,
            entry_price=entry_p,
            exit_price=exit_p,
            fx_rate=fx_rate,
            equity_change=Decimal("0")
        )

        if not is_closing:
            # OPENING / ADDING
            open_positions.append({
                'price': raw.price,
                'date': raw.timestamp,
                'qty': raw.quantity,
                'fx': fx_rate
            })
            processed.pnl = Decimal("0")

        else:
            # CLOSING
            remaining_qty = raw.quantity
            total_pnl = Decimal("0")
            
            # For Avg Entry Price Calculation
            total_matched_cost_basis = Decimal("0")
            total_matched_abs_qty = Decimal("0")
            
            # While we have qty to close and positions to close against
            while remaining_qty != 0 and open_positions:
                match_pos = open_positions[0]
                match_qty = match_pos['qty'] # e.g. +10 (Long)
                
                # Determine how much we can close
                # If closing (Sell -10) against Long (+10):
                #   We need to neutralize. 
                #   If abs(remaining) >= abs(match): Full match of this pos chunk
                #   Else: Partial match
                
                # Math:
                # If signs differ, we are reducing magnitude.
                # We want to know the portion of 'match_qty' that is consumed by 'remaining_qty'.
                
                # Case 1: Sell (-5) against Long (+10) -> Match -5. Remainder 0. Pos becomes +5.
                # Case 2: Sell (-20) against Long (+10) -> Match -10. Remainder -10. Pos removed.
                
                if abs(remaining_qty) >= abs(match_qty):
                    # Full consumption of this position chunk
                    consumed = match_qty # The full +10
                    # Remove from stack
                    open_positions.pop(0)
                    # Adjust remainder: -20 - (-10) = -10 (correct direction)
                    # Wait, if remaining is -20 and we consume +10 (which is an opposite), 
                    # effectively we covered 10 units. 
                    # Logic: 
                    #   qty_to_process = -match_qty (The amount of 'remaining' needed to offset)
                    qty_to_process = -match_qty 
                    
                    # BUT wait, "remaining" is the active order. "match" is passive.
                    # We are executing 'remaining'.
                    # Amount of 'remaining' used = 'match_qty' * -1? No.
                    # Simpler:
                    #   We perform a netted addition.
                    #   If we fully verify the match, the amount of Trade Quantity used is -(amount of Open Quantity found).
                    
                    fill_qty = -match_qty # e.g. -10
                    remaining_qty -= fill_qty # -20 - (-10) = -10. Correct.
                    
                    
                    # Calculate PnL separately for Long vs Short based on the OPENING position direction
                    # match_qty determines the direction of the trade we are closing.
                    # If match_qty > 0: It was a Long position (Buy). We are Selling.
                    #   PnL = (ExitPrice * ExitFX - EntryPrice * EntryFX) * NumUnits
                    # If match_qty < 0: It was a Short position (Sell). We are Covering.
                    #   PnL = (EntryPrice * EntryFX - ExitPrice * ExitFX) * NumUnits
                    
                    # The number of units being closed is the absolute amount of 'fill_qty' (or equal to abs(match_qty) in this full match case)
                    units = abs(fill_qty)
                    
                    # Cost Basis Accumulation
                    total_matched_cost_basis += (match_pos['price'] * units)
                    total_matched_abs_qty += units
                    
                    if match_qty > 0: # Long
                        exit_val = raw.price * fx_rate
                        entry_val = match_pos['price'] * match_pos['fx']
                        chunk_pnl = (exit_val - entry_val) * units
                    else: # Short
                        exit_val = raw.price * fx_rate
                        entry_val = match_pos['price'] * match_pos['fx']
                        chunk_pnl = (entry_val - exit_val) * units
                        
                    total_pnl += chunk_pnl
                    
                else:
                    # Partial consumption of position chunk
                    # Sell (-5) against Long (+10).
                    # We use all of 'remaining_qty'.
                    fill_qty = remaining_qty # -5
                    
                    # How much of match_qty is consumed? The opposite of fill_qty.
                    consumed_match = -fill_qty # +5
                    
                    # Update position
                    match_pos['qty'] -= consumed_match # 10 - 5 = 5.
                    # Remainder done
                    remaining_qty = Decimal("0")
                    
                    # PnL - Apply same directional logic
                    units = abs(consumed_match)

                    # Cost Basis Accumulation
                    total_matched_cost_basis += (match_pos['price'] * units)
                    total_matched_abs_qty += units

                    if match_pos['qty'] + consumed_match > 0: 
                        # Wait, we modified match_pos['qty'] already?
                        # Above: match_pos['qty'] -= consumed_match
                        # Check original sign or check current sign? 
                        # 'match_pos' contains the REMAINDER.
                        # We need to know the original direction.
                        # If match_pos['qty'] is now 5 (was 10), it's > 0 -> Long.
                        # If match_pos['qty'] is now -5 (was -10), it's < 0 -> Short.
                        # Safe to check current sign because we never cross zero in a partial consumption.
                        is_long = match_pos['qty'] > 0
                    else:
                        is_long = match_pos['qty'] > 0 # Or check consumed_match sign?
                        # consumed_match has same sign as the position being closed?
                        # consumed_match = -fill_qty.
                        # If fill is -5 (Sell), consumed is +5. Original pos was +10. matches.
                        is_long = consumed_match > 0

                    if is_long: # Long
                        exit_val = raw.price * fx_rate
                        entry_val = match_pos['price'] * match_pos['fx']
                        chunk_pnl = (exit_val - entry_val) * units
                    else: # Short (-Entry - -Exit) or (Entry - Exit)
                        exit_val = raw.price * fx_rate
                        entry_val = match_pos['price'] * match_pos['fx']
                        chunk_pnl = (entry_val - exit_val) * units
                        
                    total_pnl += chunk_pnl

            # If remaining_qty is still not 0 (Flip), add remainder as new position
            if remaining_qty != 0:
                open_positions.append({
                    'price': raw.price,
                    'date': raw.timestamp,
                    'qty': remaining_qty,
                    'fx': fx_rate
                })
            
            # Set Avg Entry Price on result
            if total_matched_abs_qty > 0:
                processed.entry_price = total_matched_cost_basis / total_matched_abs_qty
                
            processed.pnl = total_pnl
            self.state.cum_trading_pnl += total_pnl
            
            if total_pnl > 0:
                self.state.gross_profit += total_pnl
                self.state.wins += 1
            elif total_pnl < 0:
                self.state.gross_loss += abs(total_pnl)
                self.state.losses += 1

        # Updates for all trades
        # Equity Change? For "Total Equity", we need the Cash impact.
        # But req says: Total Equity = Inflows - Outflows + Realized PnL.
        # So for a Trade, the impact to this metric is JUST the PnL.
        processed.equity_change = processed.pnl
        self.state.total_equity += processed.pnl
        
        self._update_metrics(processed)
        return processed

    def _process_transfer(self, raw: RawEvent) -> ProcessedEvent:
        """ Handles Inflow/Outflow. """
        processed = ProcessedEvent(
            event_id=raw.event_id,
            date=raw.timestamp,
            type=raw.type,
            symbol=None,
            # amount=raw.amount, ProcessedEvent does not have 'amount' field.
            # Using equity_change to store the value. 
            equity_change=raw.amount # Transfers change equity directly
        )
        
        self.state.total_equity += raw.amount
        
        # Track Cum Inflow (External Money)
        if raw.type == TransactionType.INFLOW:
             self.state.cum_inflow += raw.amount
        elif raw.type == TransactionType.OUTFLOW:
             # Outflow is negative amount, so adding it reduces net inflow
             self.state.cum_inflow += raw.amount
             
        self._update_metrics(processed)
        return processed

    def _update_metrics(self, processed: ProcessedEvent):
        """ Updates cumulative metrics on the event. """
        processed.total_equity = self.state.total_equity
        processed.equity_curve = self.state.cum_trading_pnl
        processed.cum_inflow = self.state.cum_inflow
        
        # Win Rate
        total_trades = self.state.wins + self.state.losses
        if total_trades > 0:
            processed.cum_win_rate = (self.state.wins / total_trades) * 100.0
        else:
            processed.cum_win_rate = 0.0
            
        # Profit Factor
        if self.state.gross_loss == 0:
            processed.cum_profit_factor = float('inf') if self.state.gross_profit > 0 else 0.0
        else:
            processed.cum_profit_factor = float(self.state.gross_profit / self.state.gross_loss)
            
        # Drawdown (Based on Adjusted Equity = Total Equity - Cum Inflow)
        # This removes the effect of Cash Inflows/Outflows from the Drawdown calculation.
        # Adjusted Equity roughly tracks Cumulative PnL + Dividends.
        
        adj_equity = self.state.total_equity - self.state.cum_inflow
        
        if adj_equity > self.state.adjusted_equity_high_watermark:
            self.state.adjusted_equity_high_watermark = adj_equity
        
        # Only calculate Drawdown if we have established a positive High Watermark of earnings.
        # If HWM <= 0 (i.e. we are overall negative or zero profit), Drawdown is 0.
        if self.state.adjusted_equity_high_watermark > 0:
            dd = (self.state.adjusted_equity_high_watermark - adj_equity) / self.state.adjusted_equity_high_watermark
            processed.drawdown = float(dd) * 100.0 * -1.0 
        else:
            processed.drawdown = 0.0
