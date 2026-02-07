import csv
from decimal import Decimal
from typing import List, Dict
from datetime import datetime

from .types import EventWithSnapshot

class CsvOutputGenerator:
    def __init__(self):
        self.fieldnames = [
            'date', 'time', 'Trade_PnL', 'Trade_R', 'Fee', 'Cashflow', 
            'Dividend', 'Equity', 'Cash', 'Total_Assets', 'Drawdown', 
            'Sum_Deposit', 'Sum_Withdrawal', 'Sum_Dividend', 'Trade_Count', 
            'event', 'symbol', 'quantity', 'price', 
            # Extra columns possibly needed by dashboard filtering
            # 'setup', 'duration'? Data loader doesn't use them explicitly but they might be useful.
            # Keeping it minimal to what data_loader.py uses.
        ]

    def _fmt(self, d: Decimal) -> str:
        if d is None: return "0.00"
        return f"{d:.2f}"

    def generate(self, history: List[EventWithSnapshot]) -> str:
        # We return string instead of writing to file directly to matching interface?
        # XmlGenerator returns string.
        # But here we probably want to write closely.
        # Let's return stringbuffer content to allow main to write it.
        import io
        output = io.StringIO()
        
        # Use semicolon separator as per data_loader.py: pd.read_csv("journal.csv", sep=";")
        writer = csv.DictWriter(output, fieldnames=self.fieldnames, delimiter=';')
        writer.writeheader()
        
        # State Tracking
        prev_realized_pnl = Decimal("0")
        
        # We need to track cumulative types locally if snapshot doesn't have them broken down
        # Snapshot has inflows_total (Net Deposit + Dividend).
        # We need sum_deposit, sum_withdrawal, sum_dividend separately.
        sum_deposit = Decimal("0")
        sum_withdrawal = Decimal("0")
        sum_dividend = Decimal("0")
        
        # High Water Mark Tracking for Drawdown Amount
        hwm = Decimal("-999999999") # Start low or 0? 
        # Actually High Water Mark should start at 0 if no funds. 
        # First deposit sets High Water Mark.
        # Logic: adj_equity = Equity - Inflows.
        # If first event is Deposit 1000. Equity 1000. Inflows 1000. Adj = 0.
        # High Water Mark = 0.
        # If PnL +10. Equity 1010. Inflows 1000. Adj = 10. High Water Mark = 10.
        # If PnL -5. Equity 1005. Inflows 1000. Adj = 5. Drawdown = 5 - 10 = -5.
        
        hwm = Decimal("0")
        
        for item in history:
            tnx = item.transaction
            snap = item.snapshot
            perf = snap.performance
            
            t_type = tnx.type.upper()
            
            # --- Cumulative Updates ---
            if t_type == "DEPOSIT":
                sum_deposit += tnx.quantity
            elif t_type == "WITHDRAWAL":
                # Assuming quantity is positive for withdrawal amount
                sum_withdrawal += tnx.quantity
            elif t_type == "DIVIDEND" or t_type == "DIV":
                sum_dividend += tnx.quantity
            
            # --- Trade PnL (Net) ---
            # Change in Realized PnL
            current_realized = perf.realized_pnl
            trade_pnl = current_realized - prev_realized_pnl
            prev_realized_pnl = current_realized
            
            # If strictly a trade event, we can use this delta.
            # If it's a Deposit, realized pnl shouldn't change, so delta is 0.
            
            # --- Drawdown Amount ---
            curr_equity = snap.total_equity
            curr_inflows = snap.inflows # This matches sum_deposit + sum_dividend - sum_withdrawal theoretically
            
            # --- Total_Assets = Position Value (Equity - Cash) ---
            # Per Dashboard Tooltip: "Liquidationswert aller offenen Positionen (ohne Cash)"
            total_assets = snap.market_value_total  # This is the signed sum of all position values
            
            adj_equity = curr_equity - curr_inflows
            
            if adj_equity > hwm:
                hwm = adj_equity
                
            drawdown_amt = adj_equity - hwm # Always <= 0
            
            # --- Fee ---
            # Current transaction fee
            fee = tnx.commission
            
            # --- Value to use for Price/Qty ---
            # For charts, maybe useful checking 'price' column behavior
            
            row = {
                'date': tnx.date.strftime("%Y-%m-%d"),
                'time': tnx.date.strftime("%H:%M:%S"),
                'Trade_PnL': self._fmt(trade_pnl),
                'Trade_R': "0",
                'Fee': self._fmt(fee),
                'Cashflow': "0.00", # Default
                'Dividend': "0.00",
                'Equity': self._fmt(curr_equity),
                'Cash': self._fmt(snap.cash),
                'Total_Assets': self._fmt(total_assets),  # Position value only, not Equity
                'Drawdown': self._fmt(drawdown_amt),
                'Sum_Deposit': self._fmt(sum_deposit),
                'Sum_Withdrawal': self._fmt(sum_withdrawal),
                'Sum_Dividend': self._fmt(sum_dividend),
                'Trade_Count': perf.closed_trades_count,
                'event': t_type.lower(),
                'symbol': tnx.symbol if tnx.symbol else "",
                'quantity': self._fmt(tnx.quantity),
                'price': self._fmt(tnx.price)
            }
            
            # Specific Overrides
            if t_type == "DEPOSIT":
                row['Cashflow'] = self._fmt(tnx.quantity)
            elif t_type == "WITHDRAWAL":
                row['Cashflow'] = self._fmt(-tnx.quantity)
            elif t_type == "DIVIDEND" or t_type == "DIV":
                row['Cashflow'] = self._fmt(tnx.quantity)
                row['Dividend'] = self._fmt(tnx.quantity)
                # Event naming convention for data_loader
                row['event'] = 'dividend'
            
            # Fix event name for data_loader matching (sell/buy)
            if t_type == "BUY": row['event'] = "buy"
            elif t_type == "SELL": row['event'] = "sell"
            
            writer.writerow(row)
            
        return output.getvalue()
