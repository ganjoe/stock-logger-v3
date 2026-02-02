import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List
from decimal import Decimal
from .domain import PortfolioSnapshot, PerformanceMetrics, EventSnapshot

class XmlOutputGenerator:
    def _fmt(self, d: Decimal) -> str:
        """ Format decimal to string (2 places standard) """
        if d is None: return "0.00"
        return f"{d:.2f}"

    def _write_performance(self, parent: ET.Element, metrics: PerformanceMetrics):
        perf = ET.SubElement(parent, "Performance")
        ET.SubElement(perf, "TotalRealizedPnL", currency="EUR").text = self._fmt(metrics.total_realized_pnl)
        ET.SubElement(perf, "TotalFees", currency="EUR").text = self._fmt(metrics.total_fees)
        
        # F-CALC-050 - PnL Breakdown (ICD-CALC-010)
        ET.SubElement(perf, "Trading", currency="EUR").text = self._fmt(metrics.pnl_breakdown.trading_pnl)
        ET.SubElement(perf, "Real", currency="EUR").text = self._fmt(metrics.pnl_breakdown.real_pnl)
        ET.SubElement(perf, "Accounting", currency="EUR").text = self._fmt(metrics.pnl_breakdown.accounting_pnl)
        
        ET.SubElement(perf, "WinRate", unit="Percent").text = self._fmt(metrics.win_rate)
        ET.SubElement(perf, "ProfitFactor").text = self._fmt(metrics.profit_factor)
        ET.SubElement(perf, "MaxDrawdown", unit="Percent").text = self._fmt(metrics.max_drawdown)
        ET.SubElement(perf, "Expectancy", currency="EUR").text = self._fmt(metrics.expectancy)
        
        # NEW: F-CALC-130 - Total Trades Statistics
        trades_elem = ET.SubElement(perf, "TotalTrades")
        ET.SubElement(trades_elem, "ClosedTrades").text = str(metrics.total_closed_trades)
        ET.SubElement(trades_elem, "OpenPositions").text = str(metrics.total_open_positions)
        ET.SubElement(trades_elem, "Transactions").text = str(metrics.total_transactions)

    def generate(self, events: List[EventSnapshot], metrics: PerformanceMetrics) -> str:
        root = ET.Element("PortfolioHistory")
        
        # 1. Performance Summary
        self._write_performance(root, metrics)

        # 2. Event Log (<Change>)
        # No <History> wrapper as per ICD
        
        for event in events:
            # <Change id="..."> e.g. from event.event_id
            change_elem = ET.SubElement(root, "Change", id=event.event_id)
            
            # Event Metadata
            ET.SubElement(change_elem, "Timestamp").text = event.timestamp.isoformat()
            ET.SubElement(change_elem, "Type").text = event.event_type
            
            if event.symbol:
                ET.SubElement(change_elem, "Symbol").text = event.symbol
                # Only if stock trade/div?
                
            if event.quantity is not None:
                ET.SubElement(change_elem, "Quantity").text = self._fmt(event.quantity)
                
            # MarketValue of the Event (e.g. Price or Amount)
            if event.market_value is not None:
                mv_elem = ET.SubElement(change_elem, "MarketValue")
                ET.SubElement(mv_elem, "Value").text = self._fmt(event.market_value)
                # OHLC placeholder?
                # ET.SubElement(mv_elem, "OHLC").text = "..."

            # 3. Snapshot Content
            snap = event.snapshot
            snap_elem = ET.SubElement(change_elem, "Snapshot")
            
            ET.SubElement(snap_elem, "Inflows", currency="EUR").text = "0.00" # TODO: Track cumulative inflows?
            # Calculator tracks total_deposits_eur, but PortfolioSnapshot struct doesn't have it?
            # We defined PortfolioSnapshot to have total_equity, cash, etc.
            # Let's check Domain? 'invested_capital' was defined.
            # If Inflows not in Snapshot struct, we skip or use InvestedCapital?
            # We will fix Inflows later if needed.
            
            ET.SubElement(snap_elem, "Cash", currency="EUR").text = self._fmt(snap.cash_balance)
            ET.SubElement(snap_elem, "Invested", currency="EUR").text = self._fmt(snap.invested_capital)
            ET.SubElement(snap_elem, "TotalEquity", currency="EUR").text = self._fmt(snap.total_equity)
            ET.SubElement(snap_elem, "Drawdown", unit="Percent").text = self._fmt(snap.drawdown)
            
            # Performance in Snapshot (ICD Compliance)
            if hasattr(snap, 'performance') and snap.performance:
                 self._write_performance(snap_elem, snap.performance)
            
            # SubPositions -> Positions
            pos_container = ET.SubElement(snap_elem, "Positions")
            for p in snap.open_positions:
                p_elem = ET.SubElement(pos_container, "Position")
                
                ET.SubElement(p_elem, "Symbol").text = p.symbol
                ET.SubElement(p_elem, "ISIN").text = p.isin
                ET.SubElement(p_elem, "Quantity").text = self._fmt(p.quantity)
                ET.SubElement(p_elem, "AvgEntryPrice").text = self._fmt(p.avg_entry_price)
                ET.SubElement(p_elem, "Value", currency="EUR").text = self._fmt(p.market_value) # MarketValue
                ET.SubElement(p_elem, "AccumulatedFees").text = self._fmt(p.accumulated_fees)
                ET.SubElement(p_elem, "Currency").text = p.currency
                ET.SubElement(p_elem, "ExchangeRate").text = self._fmt(p.exchange_rate)
                # NEW: F-CALC-120 - Holding Time
                ET.SubElement(p_elem, "HoldingDays").text = str(p.holding_days)
                
                # Performance node on Position level?
                perf_pos = ET.SubElement(p_elem, "Performance")
                # We have 'unrealized_pnl' in OpenPosition
                ET.SubElement(perf_pos, "UnrealizedPnL", currency="EUR").text = self._fmt(p.unrealized_pnl)

        # Pretty Print
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
