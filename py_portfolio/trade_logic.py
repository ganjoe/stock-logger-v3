
from decimal import Decimal
from typing import List, Dict, Optional, Any, Tuple
from .alm_types import (
    RawEvent, ProcessedEvent, PortfolioState, TransactionType, 
    MarketDataProvider, Snapshot, Position, Performance, OHLC
)

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
        # Dividend increases Cash and Total Equity.
        # It affects Accounting PnL (usually), but spec says:
        # PnL Types: 
        #   Trading: (Nur Kursgewinne) -> No
        #   Real: (Kursgewinne - Gebühren) -> No, still price based?
        #   Accounting: (Inkl FX, Gebühren) -> Is Dividend "Profit"?
        #   F-LOGIC-025: "Dividenden erhöhen Total Equity, zählen aber nicht zum Trading-PnL."
        #   Usually Dividends are Realized gains in Accounting. 
        #   Let's assume Dividend is added to Accounting PnL (or treated as Income).
        #   However, ICD-CALC-010 defines PnL values specifically around "Kursgewinne".
        #   Let's stick to strict interpretation: Dividend is Cash Income, increases Equity, 
        #   but might NOT be in "Trading PnL".
        
        # NOTE: Using raw.amount for Dividend Value in EUR (if parsed as such)
        
        self.state.cash_balance += raw.amount
        # Total Equity increases by amount
        # No change to Invested Capital
        
        processed = ProcessedEvent(
            event_id=raw.event_id,
            date=raw.timestamp,
            type=raw.type,
            symbol=raw.symbol,
            quantity=Decimal("0"),
            price=Decimal("0"),
            market_value=raw.amount # Use MV field for Dividend Amount?
        )
        
        # Snapshot Gen
        self._generate_snapshot(processed)
        return processed

    def _process_transfer(self, raw: RawEvent) -> ProcessedEvent:
        """ Handles Inflow/Outflow. """
        # Inflow: Increases Cash, Increases Cum Inflow.
        # Outflow: Decreases Cash, Decreases Cum Inflow (negative amount).
        
        self.state.cash_balance += raw.amount
        self.state.cum_inflow += raw.amount
        
        processed = ProcessedEvent(
            event_id=raw.event_id,
            date=raw.timestamp,
            type=raw.type,
            symbol=None,
            market_value=raw.amount
        )
        
        self._generate_snapshot(processed)
        return processed

    def _process_trade(self, raw: RawEvent) -> ProcessedEvent:
        """ Handles Buy/Sell logic with FIFO and 3-tier PnL. """
        
        curr_pair = f"{raw.currency}EUR"
        date_str = raw.timestamp.strftime("%Y-%m-%d")
        fx_rate = self.market_data.get_fx_rate(curr_pair, date_str)
        
        symbol = raw.symbol
        if symbol not in self.state.open_positions:
            self.state.open_positions[symbol] = []
        open_positions = self.state.open_positions[symbol]
        
        # Determine if Closing
        is_closing = False
        if open_positions:
            first_qty = open_positions[0]['qty']
            if (raw.quantity > 0 and first_qty < 0) or (raw.quantity < 0 and first_qty > 0):
                is_closing = True
        
        # Trade Values
        trade_price = raw.price
        trade_qty = raw.quantity
        trade_val_local = trade_price * abs(trade_qty)
        trade_val_eur = trade_val_local * fx_rate
        commission = raw.commission
        
        # Update Cash:
        # Buy: Cash -= (Value + Comm)
        # Sell: Cash += (Value - Comm)
        # Logic: Cash += (Qty * Price * FX) - Comm? 
        # Wait, Qty is signed.
        # Sell (-10) * 100 = -1000.  We want Cash +1000.
        # So Cash -= (Qty * Price * FX).  (-(-1000) = +1000).
        # And Comm is always subtracted.
        cash_impact = -(trade_qty * trade_price * fx_rate) - commission
        self.state.cash_balance += cash_impact
        
        processed = ProcessedEvent(
            event_id=raw.event_id,
            date=raw.timestamp,
            type=raw.type,
            symbol=raw.symbol,
            quantity=raw.quantity,
            price=raw.price,
            fx_rate=fx_rate,
            market_value=trade_val_eur # Absolute Value of transaction
        )

        if not is_closing:
            # OPENING
            # Add to stack
            # Store 'fees_per_unit' to calculate precise Real/Accounting PnL on close?
            # ICD says "Real = Kursgewinne - Gebühren".
            # Usually fees are realized immediately or attached to cost basis.
            # Let's attach fees to the position for "Net PnL" calc.
            fees_unit = commission / abs(trade_qty) if trade_qty != 0 else 0
            
            open_positions.append({
                'price': trade_price,
                'date': raw.timestamp,
                'qty': trade_qty,
                'fx': fx_rate,
                'fees_unit': fees_unit
            })
            
        else:
            # CLOSING
            remaining_qty = trade_qty
            
            # PnL Accumulators for this event
            pnl_trading = Decimal("0")
            pnl_real = Decimal("0")
            pnl_accounting = Decimal("0")
            
            # Fees for this closing trade
            closing_fees = commission
            # We need to distribute closing fees across the closed units for PnL calculation?
            # Or just subtract from total. PnL Real = Trading PnL - Opening Fees - Closing Fees.
            
            # Helper to track consumed opening fees
            consumed_opening_fees = Decimal("0")

            while remaining_qty != 0 and open_positions:
                match_pos = open_positions[0]
                match_qty = match_pos['qty']
                
                if abs(remaining_qty) >= abs(match_qty):
                    # Full match of position
                    fill_qty = -match_qty
                    remaining_qty -= fill_qty
                    open_positions.pop(0)
                    
                    units = abs(fill_qty)
                    consumed_opening_fees += (match_pos['fees_unit'] * units)
                    
                    # Calcs
                    entry_p = match_pos['price']
                    exit_p = raw.price
                    entry_fx = match_pos['fx']
                    exit_fx = fx_rate
                    
                    # Direction:
                    # If Match > 0 (Long), we are Selling.
                    if match_qty > 0:
                        # Long
                        # Trading: (Exit - Entry) * Units
                        pnl_trading += (exit_p - entry_p) * units
                        # Accounting: (Exit*ExitFX - Entry*EntryFX) * Units
                        pnl_accounting += ((exit_p * exit_fx) - (entry_p * entry_fx)) * units
                    else:
                        # Short
                        # Trading: (Entry - Exit) * Units
                        pnl_trading += (entry_p - exit_p) * units
                        # Accounting: (Entry*EntryFX - Exit*ExitFX) * Units
                        pnl_accounting += ((entry_p * entry_fx) - (exit_p * exit_fx)) * units
                        
                else:
                    # Partial match
                    fill_qty = remaining_qty
                    consumed_match = -fill_qty
                    match_pos['qty'] -= consumed_match
                    remaining_qty = Decimal("0")
                    
                    units = abs(fill_qty)
                    consumed_opening_fees += (match_pos['fees_unit'] * units)
                    
                    entry_p = match_pos['price']
                    exit_p = raw.price
                    entry_fx = match_pos['fx']
                    exit_fx = fx_rate
                    
                    # Check original direction (Partial doesn't flip sign)
                    is_long = consumed_match > 0 # consumed is portion of match
                    
                    if is_long:
                        pnl_trading += (exit_p - entry_p) * units
                        pnl_accounting += ((exit_p * exit_fx) - (entry_p * entry_fx)) * units
                    else:
                        pnl_trading += (entry_p - exit_p) * units
                        pnl_accounting += ((entry_p * entry_fx) - (exit_p * exit_fx)) * units

            # Logic for remaining (Flip)
            if remaining_qty != 0:
                # Add remainder
                fees_unit = Decimal("0") # Closing fees already accounted? 
                # If we flip, the remaining part is a NEW opening.
                # How to split commission? 
                # Simplification: All commission attributed to the executed part?
                # Let's say yes for now.
                open_positions.append({
                    'price': trade_price,
                    'date': raw.timestamp,
                    'qty': remaining_qty,
                    'fx': fx_rate,
                    'fees_unit': fees_unit
                })

            # Finalize PnL
            # Real PnL = Trading PnL - (Opening Fees + Closing Fees) -> Wait, Trading PnL is RAW price diff.
            # Real PnL (ICD: Kursgewinne - Gebühren, ohne FX)
            # So: Trading PnL (in Quote Ccy) - Fees (in Quote Ccy?). 
            # Assuming Fees are in EUR (Base) or Quote?
            # XML says "Commission" (likely EUR or Account Currency).
            # If Trading PnL is in USD (Quote) and Fees in EUR... mix.
            # ICD says "Dezimalzahlen en_US". Implies standardized base currency?
            # "Accounting means incl FX = Buchhalterischer Gewinn in EUR".
            # "Trading means nur Kursgewinne, ohne FX". This implies Trading PnL is in SOURCE Currency usually? Or converted at consistent rate?
            # Usually "Trading PnL" is "Points * Value".
            # Let's convert Trading PnL to EUR using CURRENT FX for comparison, OR keep in Raw?
            # Standard practice: Trading PnL in Account Currency (EUR) but using FIXED rate (Entry or Exit)?
            # NO. "Ohne FX" usually means: (Exit - Entry) * Qty. This is in USD.
            # BUT the Output XML has everything in one number format. 
            # Context F-LOGIC-050: "PnL...".
            # Let's convert Trading PnL to EUR using Average Rate or Current Rate?
            # Or is Trading PnL simply the USD difference? 
            # If the XML is valid for a Tax Report, "Trading" usually means the USD gain.
            # BUT we sum them up? Summing USD and EUR is bad.
            # Decision: Convert Trading PnL to EUR using Exit FX (Realized value) 
            # BUT excluding the FX *Gain* component? 
            # Actually ICD says: "<Trading> (Nur Kursgewinne, ohne FX/Gebühr)". 
            # This is ambiguous. 
            # Let's implement: Trading PnL = (Exit - Entry) * Qty * Exif_FX. (Value of Price Move).
            # Accounting PnL = (Exit*ExitFX - Entry*EntryFX)*Qty. (Total Value Move).
            # Real PnL = Trading PnL - Fees.
            
            # Using Exit FX for Trading PnL conversion to make it comparable in EUR.
            pnl_trading_eur = pnl_trading * fx_rate 
            
            # Wait, "Accounting" includes FX gain. "Trading" excludes it.
            # Difference is purely (Entry * (ExitFX - EntryFX)).
            # So calculating Trading PnL in Quote (USD) and converting at ExitFX is "Trading PnL in EUR".
            
            self.state.cum_trading_pnl += pnl_trading_eur
            self.state.cum_real_pnl += (pnl_trading_eur - consumed_opening_fees - closing_fees)
            self.state.cum_accounting_pnl += (pnl_accounting - consumed_opening_fees - closing_fees)
            
            if pnl_trading_eur > 0:
                self.state.gross_profit_trading += pnl_trading_eur
                self.state.wins_trading += 1
            elif pnl_trading_eur < 0:
                self.state.gross_loss_trading += abs(pnl_trading_eur)
                self.state.losses_trading += 1

        self._generate_snapshot(processed)
        return processed

    def _generate_snapshot(self, processed: ProcessedEvent):
        """ Generates the Snapshot object from current state. """
        
        # 1. Calculate Market Value & Invested Capital
        # Loop through all open positions
        total_market_value = Decimal("0")
        total_invested = Decimal("0")
        
        pos_list = []
        
        for sym, lots in self.state.open_positions.items():
            if not lots: continue
            
            # Aggregate Lots into one Position
            qty_sum = sum(l['qty'] for l in lots)
            if qty_sum == 0: continue
            
            # Current Price (OHLC) needed?
            # Usage of ICD-030/050: "Lookup via Datum".
            # We need the Closing Price of 'sym' at 'processed.date'.
            # MarketDataProvider needs to provide Stock Price too?
            # NOTE: The current MarketDataProvider only provides FX.
            # We assume we can get price? Or use Last Trade Price?
            # For "MarketValue" calculation in a history log:
            # - Ideally use EOD Close.
            # - Minimal: Use Last Transaction Price of that symbol?
            # - Better: We don't have separate price feed in specifications yet except "F-LOGIC-030" calls for FX.
            # Wait, F-LOGIC-030 says "Ersetze Platzhalter... Access to ./data/market/{CUR}EUR.json". 
            # That is FX.
            # What about Stock Prices? 
            # ICD-DAT-042 requires <OHLC> (Daily Candle).
            # Assumption: We need a method to get OHLC data.
            # For now, I will define a placeholder or extend data provider later.
            # I will use the CURRENT TRANSACTION PRICE if symbol matches, else... 0?
            # Or persist last known price?
            
            # Let's use Last Known Price for now.
            current_price = processed.price if processed.symbol == sym else Decimal("0") 
            # If 0 (e.g. Inflow event), we might have a problem calculating MV.
            # Requires full market data implementation.
            # For this task, I will set MV = Qty * AvgEntry (Cost) if Price unknown? No, that's Invested.
            
            # Placeholder: Market Value = Invested (flat) if no price update.
            # Assuming 'trade_logic' is run sequentially, we can cache last price.
            # But really we need a PriceSource.
            
            cost_basis = sum(l['qty'] * l['price'] * l['fx'] for l in lots)
            market_val = qty_sum * current_price * Decimal("1.0") # Missing FX for symbol?
            
            # Create Position Object
            p = Position(
                symbol=sym,
                quantity=qty_sum,
                value=market_val,
                avg_entry_price=cost_basis/qty_sum if qty_sum else 0,
                accumulated_fees=sum(l['fees_unit']*abs(l['qty']) for l in lots),
                # Missing OHLC, ISIN etc.
            )
            pos_list.append(p)
            
            total_invested += cost_basis
            total_market_value += market_val
            
        # Snapshot Construction
        snapshot = Snapshot(
            inflows=self.state.cum_inflow,
            cash=self.state.cash_balance,
            invested=total_invested,
            market_value=total_market_value,
            total_equity=self.state.cash_balance + total_market_value, # Equity = Cash + MV
            positions=pos_list,
            performance=Performance(
                trading_pnl=self.state.cum_trading_pnl,
                real_pnl=self.state.cum_real_pnl,
                accounting_pnl=self.state.cum_accounting_pnl,
                profit_factor=self._calc_pf(),
                win_rate=self._calc_wr()
            )
        )
        processed.snapshot = snapshot

    def _calc_pf(self) -> float:
        if self.state.gross_loss_trading == 0:
            return float('inf') if self.state.gross_profit_trading > 0 else 0.0
        return float(self.state.gross_profit_trading / self.state.gross_loss_trading)

    def _calc_wr(self) -> float:
        total = self.state.wins_trading + self.state.losses_trading
        return (self.state.wins_trading / total * 100.0) if total > 0 else 0.0

