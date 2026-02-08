import os
import json
import csv
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from .models import PortfolioPosition, PortfolioSummary
from py_datafetcher.service import DataFetcherService
from py_portfolio_history.xml_parser import XmlInputParser

class PortfolioService:
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.data_fetcher = DataFetcherService()
        self.risk_file = os.path.join(self.project_root, "manual_risk_data.json")
        self.trades_file = os.path.join(self.project_root, "trades.xml")
        self.journal_file = os.path.join(self.project_root, "journal.csv")
        
    def _load_risk_data(self) -> Dict:
        """Load existing risk data from JSON file."""
        if os.path.exists(self.risk_file):
            try:
                with open(self.risk_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
        
    def _get_journal_metrics(self) -> Tuple[float, float, float]:
        """
        Reads the last line of journal.csv to extract Equity, Cash, and Total_Assets.
        Returns (Equity, Cash, Total_Assets) as floats.
        """
        if not os.path.exists(self.journal_file):
            return 0.0, 0.0, 0.0
            
        try:
            with open(self.journal_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            if len(lines) < 2:
                return 0.0, 0.0, 0.0
                
            header = lines[0].strip().split(';')
            try:
                idx_equity = header.index("Equity")
                idx_cash = header.index("Cash")
                idx_assets = header.index("Total_Assets")
            except ValueError:
                return 0.0, 0.0, 0.0
                
            last_line = lines[-1].strip()
            if not last_line and len(lines) > 2:
                last_line = lines[-2].strip()
            
            if not last_line:
                return 0.0, 0.0, 0.0
                
            parts = last_line.split(';')
            if len(parts) <= max(idx_equity, idx_cash, idx_assets):
                return 0.0, 0.0, 0.0
                
            equity = float(parts[idx_equity])
            cash = float(parts[idx_cash])
            assets = float(parts[idx_assets])
            
            return equity, cash, assets
        except Exception:
            return 0.0, 0.0, 0.0

    def calculate_avg_entry(self, tranches: List[Dict]) -> Decimal:
        """Calculate weighted average entry price."""
        if not tranches:
            return Decimal("0")
        total_qty = sum(Decimal(str(t['quantity'])) for t in tranches)
        if total_qty == 0:
            return Decimal("0")
        total_cost = sum(Decimal(str(t['quantity'])) * Decimal(str(t['price'])) for t in tranches)
        return total_cost / total_qty

    def make_position_key(self, symbol: str, date_str: str) -> str:
        """Create a consistent key for risk data lookup."""
        return f"{symbol}_{date_str}"

    def validate_stop_loss(self, direction: str, entry: float, stop: float) -> Tuple[bool, str]:
        """
        Validates stop loss logic.
        LONG: Stop must be < Entry
        SHORT: Stop must be > Entry
        Returns (is_static_risk, message)
        """
        if direction == "LONG":
            if stop < entry:
                return True, "OK"
            else:
                return False, "Trailing/Profit Stop"
        else: # SHORT
            if stop > entry:
                return True, "OK"
            else:
                return False, "Trailing/Profit Stop"

    def _parse_open_positions_from_xml(self) -> Dict:
        """Process transactions from XML to find currently open positions."""
        if not os.path.exists(self.trades_file):
            return {}
            
        parser = XmlInputParser()
        transactions = parser.parse_all(self.trades_file)
        
        positions = {}
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
                
        return positions

    def get_open_positions(self, update_prices: bool = False) -> List[PortfolioPosition]:
        """Orchestrates retrieval of positions, prices, and risk data."""
        raw_positions = self._parse_open_positions_from_xml()
        risk_data = self._load_risk_data()
        
        # Prepare lookup list for prices
        isins = [data['isin'] for data in raw_positions.values() if data.get('isin')]
        market_prices = {}
        if isins:
            for isin in isins:
                try:
                    asset = self.data_fetcher.get_asset(isin, force_update=update_prices)
                    if asset:
                        from .price_service import PriceMetadata
                        market_prices[isin] = PriceMetadata(
                            isin=asset.isin, symbol=asset.symbol, 
                            price=asset.market_price, currency=asset.currency,
                            last_update=asset.last_update, source="Service"
                        )
                except Exception:
                    pass

        result = []
        for symbol, data in raw_positions.items():
            qty = data['quantity']
            direction = "LONG" if qty > 0 else "SHORT"
            avg_entry = float(self.calculate_avg_entry(data['tranches']))
            isin = data.get('isin', '')
            
            pos_obj = PortfolioPosition(
                symbol=symbol,
                isin=isin,
                quantity=abs(float(qty)),
                raw_quantity=float(qty),
                direction=direction,
                entry_price=avg_entry,
                currency=data['currency']
            )
            
            # Market Data
            mkt_data = market_prices.get(isin)
            if mkt_data and mkt_data.price:
                pos_obj.current_price = mkt_data.price
                pos_obj.market_value = pos_obj.quantity * mkt_data.price
                pos_obj.unrealized_pl = (mkt_data.price - avg_entry) * pos_obj.raw_quantity
                if avg_entry > 0:
                    pos_obj.unrealized_pct = (pos_obj.unrealized_pl / (pos_obj.quantity * avg_entry)) * 100
            else:
                pos_obj.market_value = pos_obj.quantity * avg_entry
            
            # Risk Data
            earliest_date = min(t['date'] for t in data['tranches'])
            pos_key = self.make_position_key(symbol, earliest_date)
            
            if pos_key in risk_data:
                entry = risk_data[pos_key]
                pos_obj.stop_loss = entry.get('stop_loss', 0.0)
                pos_obj.initial_risk = entry.get('initial_risk', 0.0)
                
                if pos_obj.initial_risk and pos_obj.unrealized_pl is not None:
                    pos_obj.r_multiple = pos_obj.unrealized_pl / pos_obj.initial_risk
                
                is_static, _ = self.validate_stop_loss(direction, avg_entry, pos_obj.stop_loss)
                if is_static:
                    pos_obj.status_flags.append("OK")
                    pos_obj.is_valid = True
                else:
                    pos_obj.status_flags.append("Trail")
                    pos_obj.is_valid = False
            else:
                pos_obj.status_flags.append("Missing")
                pos_obj.is_valid = False
            
            result.append(pos_obj)
            
        return sorted(result, key=lambda x: x.symbol)

    def get_summary(self) -> PortfolioSummary:
        """Calculates the summary based on current open positions and journal data."""
        positions = self.get_open_positions(update_prices=False)
        equity, cash, total_assets = self._get_journal_metrics()
        
        sum_invested = sum(p.market_value for p in positions if p.market_value is not None)
        sum_unrealized_pl = sum(p.unrealized_pl for p in positions if p.unrealized_pl is not None)
        sum_initial_risk = sum(p.initial_risk for p in positions if p.initial_risk is not None)
        
        count_ok = sum(1 for p in positions if "OK" in p.status_flags)
        count_trail = sum(1 for p in positions if "Trail" in p.status_flags)
        count_missing = sum(1 for p in positions if "Missing" in p.status_flags)
        
        return PortfolioSummary(
            total_invested=sum_invested,
            total_unrealized_pl=sum_unrealized_pl,
            total_risk=sum_initial_risk,
            buying_power=cash,
            equity=equity,
            position_count=len(positions),
            count_ok=count_ok,
            count_trail=count_trail,
            count_missing=count_missing
        )

    def _save_risk_data(self, data: Dict):
        """Save risk data to JSON file."""
        with open(self.risk_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def update_stop_loss(self, symbol: str, new_stop: float) -> bool:
        """
        Updates the stop loss for an open position.
        Finds the position, calculates initial risk, and saves.
        """
        raw_positions = self._parse_open_positions_from_xml()
        if symbol not in raw_positions:
            return False
            
        pos_data = raw_positions[symbol]
        earliest_date = min(t['date'] for t in pos_data['tranches'])
        avg_entry = float(self.calculate_avg_entry(pos_data['tranches']))
        quantity = abs(float(pos_data['quantity']))
        
        # Calculate risk
        initial_risk = abs(avg_entry - new_stop) * quantity
        
        risk_data = self._load_risk_data()
        pos_key = self.make_position_key(symbol, earliest_date)
        
        # Update/Create entry
        from datetime import datetime
        risk_data[pos_key] = {
            "symbol": symbol,
            "entry_date": earliest_date,
            "stop_loss": new_stop,
            "initial_risk": initial_risk,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self._save_risk_data(risk_data)
        return True

    def delete_stop_loss(self, symbol: str) -> bool:
        """
        Removes the stop loss entry for an open position.
        """
        raw_positions = self._parse_open_positions_from_xml()
        if symbol not in raw_positions:
            return False
            
        pos_data = raw_positions[symbol]
        earliest_date = min(t['date'] for t in pos_data['tranches'])
        
        risk_data = self._load_risk_data()
        pos_key = self.make_position_key(symbol, earliest_date)
        
        if pos_key in risk_data:
            del risk_data[pos_key]
            self._save_risk_data(risk_data)
            return True
            
        return False
