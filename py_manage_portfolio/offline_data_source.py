"""
Offline Data Source Implementation.

This module implements PortfolioDataSource using local files:
- trades.xml / paper-trades.xml for positions
- manual_risk_data.json / paper-risk_data.json for stop-losses
- journal.csv / paper_journal.csv for account metrics
"""
import os
import json
import csv
import math
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from .data_source import PortfolioDataSource, AccountMetrics, RawPosition, StopOrder


class OfflineDataSource(PortfolioDataSource):
    """
    File-based implementation of PortfolioDataSource.
    
    Args:
        project_root: Path to project directory containing data files.
        context: "live" or "paper" - determines which files to use.
    """
    
    def __init__(self, project_root: str, context: str = "live"):
        self.project_root = os.path.abspath(project_root)
        self.context = context.lower()
        
        prefix = "paper-" if self.context == "paper" else ""
        
        # Risk Data
        self.risk_file = os.path.join(self.project_root, f"{prefix}risk_data.json")
        if self.context == "live":
            self.risk_file = os.path.join(self.project_root, "manual_risk_data.json")
        
        # Trades
        self.trades_file = os.path.join(self.project_root, f"{prefix}trades.xml")
        
        # Journal
        if self.context == "paper":
            self.journal_file = os.path.join(self.project_root, "paper_journal.csv")
        else:
            self.journal_file = os.path.join(self.project_root, "journal.csv")
    
    def get_positions(self) -> List[RawPosition]:
        """Parse trades.xml and return open positions."""
        if not os.path.exists(self.trades_file):
            return []
        
        from py_portfolio_history.xml_parser import XmlInputParser
        parser = XmlInputParser()
        transactions = parser.parse_all(self.trades_file)
        
        positions: Dict = {}
        for t in sorted(transactions, key=lambda x: x.date):
            if t.type not in ["BUY", "SELL"]:
                continue
                
            symbol = t.symbol
            qty = t.quantity
            side = 1 if t.type == "BUY" else -1
            signed_qty = qty * side
            
            if symbol not in positions:
                positions[symbol] = {
                    'quantity': Decimal("0"),
                    'tranches': [],
                    'currency': t.currency,
                    'isin': t.isin
                }
            
            pos = positions[symbol]
            current_side = 1 if pos['quantity'] >= 0 else -1
            if pos['quantity'] == 0:
                current_side = side
                
            # LIFO matching for closes
            if side == current_side:
                pos['quantity'] += signed_qty
                pos['tranches'].append({
                    'date': t.date.strftime("%Y-%m-%d"),
                    'quantity': float(qty),
                    'price': float(t.price),
                    'id': t.id
                })
            else:
                remaining = qty
                while remaining > 0 and pos['tranches']:
                    tranche = pos['tranches'][-1]
                    match_qty = min(remaining, Decimal(str(tranche['quantity'])))
                    remaining -= match_qty
                    pos['quantity'] -= match_qty * current_side
                    
                    if match_qty >= Decimal(str(tranche['quantity'])):
                        pos['tranches'].pop()
                    else:
                        tranche['quantity'] = float(Decimal(str(tranche['quantity'])) - match_qty)
                
                if remaining > 0:
                    pos['quantity'] = remaining * side
                    pos['tranches'] = [{
                        'date': t.date.strftime("%Y-%m-%d"),
                        'quantity': float(remaining),
                        'price': float(t.price),
                        'id': t.id
                    }]
            
            if pos['quantity'] == 0:
                del positions[symbol]
        
        # Convert to RawPosition objects
        result = []
        for symbol, data in positions.items():
            if data['tranches']:
                # Calculate weighted average entry
                total_qty = sum(Decimal(str(t['quantity'])) for t in data['tranches'])
                if total_qty > 0:
                    total_cost = sum(Decimal(str(t['quantity'])) * Decimal(str(t['price'])) for t in data['tranches'])
                    avg_entry = float(total_cost / total_qty)
                else:
                    avg_entry = data['tranches'][0]['price']
                
                # Get earliest entry date
                entry_date_str = data['tranches'][0]['date']
                entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
                
                result.append(RawPosition(
                    symbol=symbol,
                    isin=data.get('isin'),
                    quantity=float(abs(data['quantity'])),
                    entry_price=avg_entry,
                    entry_date=entry_date,
                    currency=data.get('currency', 'USD')
                ))
        
        return result
    
    def get_stop_losses(self) -> Dict[str, StopOrder]:
        """Load stop-loss data from JSON file."""
        if not os.path.exists(self.risk_file):
            return {}
        
        try:
            with open(self.risk_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception:
            return {}
        
        result = {}
        for key, data in raw_data.items():
            # Key format: SYMBOL_DATE or just SYMBOL
            symbol = key.split('_')[0] if '_' in key else key
            result[symbol] = StopOrder(
                symbol=symbol,
                stop_price=data.get('stop_loss', 0.0),
                initial_risk=data.get('initial_risk')
            )
        
        return result
    
    def get_account_metrics(self) -> AccountMetrics:
        """Read last line of journal.csv for account metrics."""
        if not os.path.exists(self.journal_file):
            return AccountMetrics(equity=0.0, cash=0.0, exposure=0.0)
        
        try:
            with open(self.journal_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if len(lines) < 2:
                return AccountMetrics(equity=0.0, cash=0.0, exposure=0.0)
            
            # Parse header
            header = lines[0].split(';')
            col_map = {name.strip(): i for i, name in enumerate(header)}
            
            idx_equity = col_map.get("Equity")
            idx_cash = col_map.get("Cash")
            idx_assets = col_map.get("Total_Assets")
            
            if idx_equity is None or idx_cash is None or idx_assets is None:
                return AccountMetrics(equity=0.0, cash=0.0, exposure=0.0)
            
            # Read last line
            parts = lines[-1].split(';')
            
            def get_val(idx):
                if idx < len(parts):
                    val = parts[idx].strip()
                    return float(val.replace(',', '.')) if val else 0.0
                return 0.0
            
            return AccountMetrics(
                equity=get_val(idx_equity),
                cash=get_val(idx_cash),
                exposure=get_val(idx_assets)
            )
        except Exception:
            return AccountMetrics(equity=0.0, cash=0.0, exposure=0.0)
    
    def set_stop_loss(self, symbol: str, stop_price: float) -> bool:
        """Save or update stop-loss in risk data JSON."""
        try:
            data = {}
            if os.path.exists(self.risk_file):
                with open(self.risk_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            # Find existing key for symbol or create new
            existing_key = None
            for key in data.keys():
                if key.startswith(symbol + '_') or key == symbol:
                    existing_key = key
                    break
            
            if existing_key:
                data[existing_key]['stop_loss'] = stop_price
            else:
                data[symbol] = {'stop_loss': stop_price}
            
            with open(self.risk_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            
            return True
        except Exception:
            return False
    
    def close_position(self, symbol: str) -> bool:
        """Remove a position from paper-trades.xml (paper mode only)."""
        if self.context != "paper" or not os.path.exists(self.trades_file):
            return False
        
        try:
            tree = ET.parse(self.trades_file)
            root = tree.getroot()
            trades_node = root.find("Trades")
            if trades_node is None:
                return False
            
            removed = False
            for t in list(trades_node.findall("Trade")):
                instr = t.find("Instrument/Symbol")
                if instr is not None and instr.text == symbol:
                    trades_node.remove(t)
                    removed = True
            
            if removed:
                tree.write(self.trades_file, encoding="utf-8", xml_declaration=True)
                # Also remove from risk data
                self._delete_stop_loss(symbol)
            
            return removed
        except Exception:
            return False
    
    def add_position(self, symbol: str, entry_price: float, stop_loss: float,
                     quantity: float, **kwargs) -> dict:
        """Add a position to paper-trades.xml (paper mode only)."""
        if self.context != "paper":
            raise NotImplementedError("add_position only supported in paper context")
        
        qty = int(quantity) if quantity > 0 else 0
        if qty <= 0:
            return {"error": "Quantity must be positive"}
        
        try:
            if os.path.exists(self.trades_file):
                tree = ET.parse(self.trades_file)
                root = tree.getroot()
            else:
                root = ET.Element("TradeLog")
                tree = ET.ElementTree(root)
            
            trades_node = root.find("Trades")
            if trades_node is None:
                trades_node = ET.Element("Trades")
                root.insert(0, trades_node)
            
            trade_id = f"PAPER_{symbol}_{int(datetime.now().timestamp())}"
            trade_node = ET.SubElement(trades_node, "Trade", id=trade_id, isin=f"PAPER_{symbol}")
            
            meta_node = ET.SubElement(trade_node, "Meta")
            ET.SubElement(meta_node, "Date").text = datetime.now().strftime("%d.%m.%Y")
            ET.SubElement(meta_node, "Time").text = datetime.now().strftime("%H:%M:%S")
            
            instr_node = ET.SubElement(trade_node, "Instrument")
            ET.SubElement(instr_node, "Symbol").text = symbol
            ET.SubElement(instr_node, "Currency").text = "USD"
            
            exec_node = ET.SubElement(trade_node, "Execution")
            ET.SubElement(exec_node, "Quantity").text = str(qty).replace('.', ',')
            ET.SubElement(exec_node, "Price").text = str(entry_price).replace('.', ',')
            ET.SubElement(exec_node, "Commission").text = "0,00"
            ET.SubElement(exec_node, "Proceeds").text = str(-(qty * entry_price)).replace('.', ',')
            
            tree.write(self.trades_file, encoding="utf-8", xml_declaration=True)
            
            # Set stop loss
            self.set_stop_loss(symbol, stop_loss)
            
            # Update journal
            self._update_paper_journal(qty * entry_price)
            
            return {
                "symbol": symbol,
                "qty": qty,
                "entry": entry_price,
                "stop": stop_loss,
                "invested": qty * entry_price
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _delete_stop_loss(self, symbol: str):
        """Remove stop-loss entry from risk data."""
        if not os.path.exists(self.risk_file):
            return
        
        try:
            with open(self.risk_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            keys_to_remove = [k for k in data.keys() if k.startswith(symbol + '_') or k == symbol]
            for key in keys_to_remove:
                del data[key]
            
            with open(self.risk_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
        except Exception:
            pass
    
    def _update_paper_journal(self, added_exposure: float):
        """Update paper_journal.csv with new exposure."""
        if self.context != "paper":
            return
        
        metrics = self.get_account_metrics()
        equity = metrics.equity if metrics.equity > 0 else 10000.0
        new_exposure = metrics.exposure + added_exposure
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        cash = equity - new_exposure
        
        write_header = not os.path.exists(self.journal_file)
        
        with open(self.journal_file, 'a', encoding='utf-8') as f:
            if write_header:
                f.write("Date;Equity;Cash;Total_Assets\n")
            f.write(f"{date_str};{equity:.2f};{cash:.2f};{new_exposure:.2f}\n")
