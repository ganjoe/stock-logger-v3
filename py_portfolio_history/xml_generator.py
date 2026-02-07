import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Any
from decimal import Decimal
from datetime import datetime

# Use new types
from .types import PortfolioSnapshot, PerformanceMetrics, Transaction, EventWithSnapshot

class XmlOutputGenerator:
    def _fmt(self, d: Decimal) -> str:
        """ Format decimal to string (2 places standard) """
        if d is None: return "0.00"
        return f"{d:.2f}"

    def _write_performance(self, parent: ET.Element, metrics: PerformanceMetrics):
        perf = ET.SubElement(parent, "Performance")
        
        # ICD-CALC-010: Trading, Real, Accounting (Cumulative)
        ET.SubElement(perf, "Trading", currency="EUR").text = self._fmt(metrics.trading_pnl)
        ET.SubElement(perf, "Real", currency="EUR").text = self._fmt(metrics.realized_pnl)
        ET.SubElement(perf, "Accounting", currency="EUR").text = self._fmt(metrics.accounting_pnl)
        
        # Extra stats
        ET.SubElement(perf, "TotalFees", currency="EUR").text = self._fmt(metrics.fees_total)
        # Inflows total is mainly a snapshot metric, but maybe useful here?
        # ICD-Calcs usually focus on PnL
        
        # KPIs
        ET.SubElement(perf, "WinRate", unit="Percent").text = self._fmt(Decimal(metrics.win_rate))
        ET.SubElement(perf, "ProfitFactor").text = self._fmt(Decimal(metrics.profit_factor))
        # Drawdown is snapshot state usually, MaxDD on summary?
        # metrics doesn't track MaxDD anymore in calculator? 
        # Ah, calculator metrics construction didn't include MaxDD. 
        # But we can pass it if we want. Metrics struct doesn't have it in types.py? 
        # Check types.py... I didn't verify if I added MaxDD to metrics.
        # Looking at types.py step:
        # @dataclass class PerformanceMetrics: trading_pnl, ... expectancy, closed_trades_count ...
        # It MISSES max_drawdown field.
        # However, ICD-CALC-020 asks for ProfitFactor, WinRate, Expectancy. MaxDD is usually separate or in Snapshot <Drawdown>.
        # Let's stick to what's in types.py. Snapshot has Drawdown.
        
        ET.SubElement(perf, "Expectancy", currency="EUR").text = self._fmt(Decimal(metrics.expectancy))
        
        # NEW: F-CALC-130 - Total Trades Statistics
        trades_elem = ET.SubElement(perf, "TotalTrades")
        ET.SubElement(trades_elem, "ClosedTrades").text = str(metrics.closed_trades_count)
        ET.SubElement(trades_elem, "OpenPositions").text = str(metrics.open_positions_count)
        ET.SubElement(trades_elem, "Transactions").text = str(metrics.total_transactions_count)

    def generate(self, history: List[EventWithSnapshot]) -> str:
        root = ET.Element("PortfolioHistory")

        # 1. We iterate the history events
        for item in history:
            tnx = item.transaction
            snap = item.snapshot
            
            # <Change id="...">
            change_elem = ET.SubElement(root, "Change", id=str(tnx.id))
            
            # Metadata
            ET.SubElement(change_elem, "Timestamp").text = tnx.date.isoformat()
            ET.SubElement(change_elem, "Type").text = str(tnx.type)
            
            if tnx.symbol:
                ET.SubElement(change_elem, "Symbol").text = tnx.symbol
                if tnx.isin:
                    ET.SubElement(change_elem, "ISIN").text = tnx.isin
                    
            # Quantity with sign?
            # Usually input quantity was positive in types.py if we handled type by string.
            # But "Buy 10" -> +10, "Sell 10" -> 10.
            # XML output might expect sign logic or just amount?
            # Standard: positive quantity, Type determines direction.
            if tnx.quantity is not None and tnx.quantity > 0:
                ET.SubElement(change_elem, "Quantity").text = self._fmt(tnx.quantity)
            
            # MarketValue of Transaction (e.g. Price or total Amount)
            # Use price * quantity * sign?
            # ICD says "MarketValue". For a Trade, this is often the total volume.
            # Transaction has price and quantity.
            val = tnx.price * tnx.quantity
            mv_elem = ET.SubElement(change_elem, "MarketValue")
            ET.SubElement(mv_elem, "Value").text = self._fmt(val)

            # 3. Snapshot
            snap_elem = ET.SubElement(change_elem, "Snapshot")
            
            ET.SubElement(snap_elem, "Inflows", currency="EUR").text = self._fmt(snap.inflows)
            ET.SubElement(snap_elem, "Cash", currency="EUR").text = self._fmt(snap.cash)
            ET.SubElement(snap_elem, "Invested", currency="EUR").text = self._fmt(snap.invested) # Exposure
            ET.SubElement(snap_elem, "TotalEquity", currency="EUR").text = self._fmt(snap.total_equity)
            
            # Drawdown?
            # Snapshot struct missing drawdown field in types.py?
            # Let's check types.py ... PortfolioSnapshot ...
            # @dataclass PortfolioSnapshot: date, cash, invested, market_value_total, total_equity, inflows, performance, positions.
            # MISSING Drawdown!
            # I must fix types.py to include 'drawdown'.
            # Or use Calculator helper to compute it?
            # Calculator computes 'dd'. But where does it store it?
            # Calculator.py: "_create_snapshot ... returns PortfolioSnapshot".
            # It computed dd but didn't pass it if the key is missing in constructor.
            # CRITICAL: I need to update types.py first to include 'drawdown' in PortfolioSnapshot.
            
            # Assuming Drawdown exists (I will fix it next):
            if hasattr(snap, 'drawdown'):
                 ET.SubElement(snap_elem, "Drawdown", unit="Percent").text = self._fmt(snap.drawdown)

            # Performance
            self._write_performance(snap_elem, snap.performance)
            
            # Positions
            pos_container = ET.SubElement(snap_elem, "Positions")
            # Sort positions by symbol for consistent output
            sorted_positions = sorted(snap.positions.values(), key=lambda p: p.symbol)
            
            for p in sorted_positions:
                p_elem = ET.SubElement(pos_container, "Position")
                
                ET.SubElement(p_elem, "Symbol").text = p.symbol
                ET.SubElement(p_elem, "ISIN").text = p.isin
                ET.SubElement(p_elem, "Quantity").text = self._fmt(p.quantity)
                ET.SubElement(p_elem, "AvgEntryPrice").text = self._fmt(p.avg_entry_price)
                ET.SubElement(p_elem, "Value", currency="EUR").text = self._fmt(p.market_value)
                ET.SubElement(p_elem, "AccumulatedFees").text = self._fmt(p.accumulated_fees)
                ET.SubElement(p_elem, "Currency").text = p.currency
                ET.SubElement(p_elem, "ExchangeRate").text = self._fmt(p.exchange_rate)
                ET.SubElement(p_elem, "HoldingDays").text = str(p.holding_days)
                
                # Performance per position
                perf_pos = ET.SubElement(p_elem, "Performance")
                ET.SubElement(perf_pos, "UnrealizedPnL", currency="EUR").text = self._fmt(p.unrealized_pnl)

        # Pretty Print
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
