
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal
from typing import List, Optional, Any
from datetime import datetime
from .alm_types import ProcessedEvent, Snapshot, Position, Performance, OHLC

class XmlGenerator:
    """ Generates trades-history.xml from a list of ProcessedEvents. """
    
    def generate(self, events: List[ProcessedEvent], output_path: str):
        root = ET.Element("PortfolioHistory")
        
        for event in events:
            self._append_change(root, event)
            
        # Write to file with pretty print
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        
        # Minidom adds XML declaration, which is good.
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
            
    def _append_change(self, root: ET.Element, event: ProcessedEvent):
        change = ET.SubElement(root, "Change")
        change.set("id", event.event_id) # ID as Attribute per ICD-STR-010
        
        # Transaction Details: Timestamp, Type, Symbol etc.
        self._add_text(change, "Timestamp", event.date.isoformat())
        self._add_text(change, "Type", event.type.value)
        
        if event.symbol:
            self._add_text(change, "Symbol", event.symbol)
            # Placeholder for Name/Ticker if available in raw?
            self._add_text(change, "Name", event.symbol) 
            self._add_text(change, "Ticker", f"{event.symbol}.US") # Default assumption
            
        if event.quantity != 0:
            self._add_decimal(change, "Quantity", event.quantity)
            
        self._add_decimal(change, "MarketValue", event.market_value)
        
        # Snapshot
        if event.snapshot:
            self._append_snapshot(change, event.snapshot)
            
    def _append_snapshot(self, parent: ET.Element, snap: Snapshot):
        snapshot_elem = ET.SubElement(parent, "Snapshot")
        
        self._add_decimal(snapshot_elem, "Inflows", snap.inflows)
        self._add_decimal(snapshot_elem, "Cash", snap.cash)
        self._add_decimal(snapshot_elem, "Invested", snap.invested)
        
        # MarketValue Complex Structure (Value + OHLC)
        mv_elem = ET.SubElement(snapshot_elem, "MarketValue")
        self._add_decimal(mv_elem, "Value", snap.market_value)
        if snap.market_value_ohlc:
            self._append_ohlc(mv_elem, snap.market_value_ohlc)
        else:
            # Empty OHLC shell? ICD Example has 0s.
            self._append_ohlc(mv_elem, OHLC(Decimal(0), Decimal(0), Decimal(0), Decimal(0)))

        # Performance Complex Structure
        if snap.performance:
            perf_elem = ET.SubElement(snapshot_elem, "Performance")
            self._add_decimal(perf_elem, "Trading", snap.performance.trading_pnl)
            self._add_decimal(perf_elem, "Real", snap.performance.real_pnl)
            self._add_decimal(perf_elem, "Accounting", snap.performance.accounting_pnl)
            self._add_decimal(perf_elem, "ProfitFactor", Decimal(snap.performance.profit_factor))
            self._add_decimal(perf_elem, "WinRate", Decimal(snap.performance.win_rate))
            
        self._add_decimal(snapshot_elem, "TotalEquity", snap.total_equity)
        
        # Positions
        positions_elem = ET.SubElement(snapshot_elem, "Positions")
        for pos in snap.positions:
            self._append_position(positions_elem, pos)
            
    def _append_position(self, parent: ET.Element, pos: Position):
        p_elem = ET.SubElement(parent, "Position")
        
        self._add_text(p_elem, "Symbol", pos.symbol)
        self._add_text(p_elem, "ISIN", pos.isin)
        self._add_decimal(p_elem, "Quantity", pos.quantity)
        self._add_decimal(p_elem, "AvgEntryPrice", pos.avg_entry_price)
        self._add_decimal(p_elem, "Value", pos.value)
        self._add_text(p_elem, "Currency", pos.currency)
        self._add_decimal(p_elem, "ExchangeRate", pos.exchange_rate)
        self._add_decimal(p_elem, "AccumulatedFees", pos.accumulated_fees)
        self._add_decimal(p_elem, "StopLoss", pos.stop_loss)
        
        if pos.ohlc:
            self._append_ohlc(p_elem, pos.ohlc)
        else:
             self._append_ohlc(p_elem, OHLC(Decimal(0), Decimal(0), Decimal(0), Decimal(0)))

        if pos.performance:
            perf_elem = ET.SubElement(p_elem, "Performance")
            self._add_decimal(perf_elem, "Trading", pos.performance.trading_pnl)
            self._add_decimal(perf_elem, "Real", pos.performance.real_pnl)
            self._add_decimal(perf_elem, "Accounting", pos.performance.accounting_pnl)

    def _append_ohlc(self, parent: ET.Element, ohlc: OHLC):
        ohlc_elem = ET.SubElement(parent, "OHLC")
        self._add_decimal(ohlc_elem, "Open", ohlc.open)
        self._add_decimal(ohlc_elem, "High", ohlc.high)
        self._add_decimal(ohlc_elem, "Low", ohlc.low)
        self._add_decimal(ohlc_elem, "Close", ohlc.close)

    def _add_text(self, parent: ET.Element, tag: str, value: str):
        elem = ET.SubElement(parent, tag)
        elem.text = str(value)
        
    def _add_decimal(self, parent: ET.Element, tag: str, val: Any):
        elem = ET.SubElement(parent, tag)
        # Format as US Decimal (dot) with 2 decimals? ICD says "US-Float".
        if isinstance(val, Decimal):
            elem.text = f"{val:.2f}"
        else:
            elem.text = f"{val:.2f}"
