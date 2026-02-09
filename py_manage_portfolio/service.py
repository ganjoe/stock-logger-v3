import os
import json
import csv
import math
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from .models import PortfolioPosition, PortfolioSummary
from py_datafetcher.service import DataFetcherService
from py_portfolio_history.xml_parser import XmlInputParser

class PortfolioService:
    def __init__(self, project_root: str, context: str = "live"):
        self.project_root = os.path.abspath(project_root)
        self.context = context.lower()
        self.data_fetcher = DataFetcherService()
        
        prefix = "paper-" if self.context == "paper" else ""
        
        # Risk Data: manual_risk_data.json OR paper-risk_data.json
        self.risk_file = os.path.join(self.project_root, f"{prefix}manual_risk_data.json".replace("paper-manual", "paper"))
        if self.context == "paper" and "manual" not in self.risk_file:
             self.risk_file = os.path.join(self.project_root, "paper-risk_data.json")

        # Trades: trades.xml OR paper-trades.xml
        self.trades_file = os.path.join(self.project_root, f"{prefix}trades.xml")
        
        # Journal: Live journal for real, paper_journal.csv for simulation
        if self.context == "paper":
            self.journal_file = os.path.join(self.project_root, "paper_journal.csv")
        else:
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
        
    def _load_risk_settings(self) -> Dict:
        """Loads risk settings from data_risksettings.csv."""
        # Defaults for Minervini Strategy
        settings = {
            "holding_threshold": 30,
            "default_risk_pct": 1.0,
            "max_equity_risk": 1.25
        }
        path = os.path.join(self.project_root, "data_risksettings.csv")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        key = row.get("Key") or row.get("ID")
                        val = row.get("Value")
                        if key and val:
                            try:
                                if val.isdigit():
                                    settings[key] = int(val)
                                else:
                                    settings[key] = float(val.replace(',', '.'))
                            except ValueError:
                                settings[key] = val
            except:
                pass
        return settings

    def get_risk_settings(self) -> Dict:
        """Public access to risk settings."""
        return self._load_risk_settings()
 
    def _get_journal_metrics(self) -> Tuple[float, float, float]:
        """
        Reads the last line of the configured journal file to extract Equity, Cash, and Total_Assets.
        Uses header-based column lookup to support both 'journal.csv' (Live) and 'paper_journal.csv' (Paper).
        Returns (Equity, Cash, Total_Assets) as floats.
        """
        if not os.path.exists(self.journal_file):
            return 0.0, 0.0, 0.0
            
        try:
            with open(self.journal_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                
            if len(lines) < 2:
                return 0.0, 0.0, 0.0
                
            # Parse Header
            header = lines[0].split(';')
            col_map = {name.strip(): i for i, name in enumerate(header)}
            
            # Identify columns (robust to order changes)
            # Both live and paper journals use specific column names
            try:
                # Primary keys
                idx_equity = col_map.get("Equity")
                idx_cash = col_map.get("Cash")
                idx_assets = col_map.get("Total_Assets")
                
                # Validation
                if idx_equity is None or idx_cash is None or idx_assets is None:
                    # Try fallback for simple paper format without header? 
                    # No, we enforce headers now for identical processing.
                    return 0.0, 0.0, 0.0
            except:
                return 0.0, 0.0, 0.0
                
            # Read Last Line
            last_line = lines[-1]
            parts = last_line.split(';')
            
            # Safe Extraction
            def get_val(idx):
                if idx < len(parts):
                    val = parts[idx].strip()
                    return float(val.replace(',', '.')) if val else 0.0
                return 0.0

            equity = get_val(idx_equity)
            cash = get_val(idx_cash)
            assets = get_val(idx_assets)
            
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
        settings = self._load_risk_settings()
        equity, _, _ = self._get_journal_metrics()
        if equity <= 0: equity = 10000.0 # Fallback
        
        # Prepare lookup list for prices (mapping ISIN -> Ticker for Fetcher hint)
        isin_map = {data['isin']: symbol for symbol, data in raw_positions.items() if data.get('isin')}
        market_prices = {}
        if isin_map:
            for isin, ticker in isin_map.items():
                try:
                    # Provide ticker hint, especially important for PAPER trades with custom ISINs
                    asset = self.data_fetcher.get_asset(isin, ticker=ticker, force_update=update_prices)
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

            # Determine Days Held
            earliest_date_str = min(t['date'] for t in data['tranches'])
            pos_obj.entry_date = earliest_date_str
            try:
                date_obj = datetime.strptime(earliest_date_str, "%Y-%m-%d").date()
                pos_obj.days_held = (datetime.now().date() - date_obj).days
            except ValueError:
                pos_obj.days_held = 0

            # 1. Risk Data (Need this for dist_pct)
            pos_key = self.make_position_key(symbol, earliest_date_str)
            risk_entry = risk_data.get(pos_key, {})
            
            stop_val = risk_entry.get('stop_loss', 0.0)
            if stop_val is None or math.isnan(stop_val): stop_val = 0.0
            pos_obj.stop_loss = stop_val
            
            # 2. Market Data
            mkt_data = market_prices.get(isin)
            if mkt_data and mkt_data.price:
                pos_obj.current_price = mkt_data.price
                pos_obj.market_value = pos_obj.quantity * mkt_data.price
                pos_obj.unrealized_pl = (mkt_data.price - avg_entry) * pos_obj.raw_quantity
                if avg_entry > 0:
                    pos_obj.unrealized_pct = (pos_obj.unrealized_pl / (pos_obj.quantity * avg_entry)) * 100
                
                # Minervini Dist%
                if pos_obj.current_price > 0 and pos_obj.stop_loss > 0:
                    dist = abs(pos_obj.current_price - pos_obj.stop_loss)
                    pos_obj.dist_pct = (dist / pos_obj.current_price) * 100
            else:
                pos_obj.market_value = pos_obj.quantity * avg_entry
            
            # 3. Risk calculation
            risk_val = risk_entry.get('initial_risk')
            if risk_val is not None and not math.isnan(risk_val) and risk_val > 0:
                pos_obj.initial_risk = risk_val
            else:
                pos_obj.initial_risk = abs(avg_entry - pos_obj.stop_loss) * pos_obj.quantity

            if pos_obj.initial_risk > 0 and pos_obj.unrealized_pl is not None:
                pos_obj.r_multiple = pos_obj.unrealized_pl / pos_obj.initial_risk
            else:
                pos_obj.r_multiple = 0.0
                
            # Minervini Equity Metrics
            pos_obj.pos_pct = (pos_obj.market_value / equity) * 100 if equity > 0 else 0
            pos_obj.risk_pct = (pos_obj.initial_risk / equity) * 100 if equity > 0 else 0
            
            # NEW Status Logic with Emojis
            status_list = []
            price = pos_obj.current_price or avg_entry
            
            if pos_obj.stop_loss == 0:
                status_list.append("⚠️") # No Stop
            elif (direction == "LONG" and price < pos_obj.stop_loss) or (direction == "SHORT" and price > pos_obj.stop_loss):
                status_list.append("🔴") # Broken
            elif (direction == "LONG" and price > avg_entry) or (direction == "SHORT" and price < avg_entry):
                status_list.append("🟢") # Profit (with Stop)
            else:
                status_list.append("🟡") # Loss (with Stop)
                
            if pos_obj.days_held > settings.get("holding_threshold", 30):
                status_list.append("⏳") # Time Stop
                
            pos_obj.status_flags = status_list
            pos_obj.is_valid = (pos_obj.stop_loss > 0)
            
            result.append(pos_obj)
            
        return sorted(result, key=lambda x: x.symbol)

    def get_summary(self) -> PortfolioSummary:
        """Calculates the summary based on current open positions and journal data."""
        positions = self.get_open_positions(update_prices=False)
        equity, cash, total_assets = self._get_journal_metrics()
        
        # Fallback logic
        if equity <= 0:
            if self.context == "paper":
                # For paper, try to inherit from live, otherwise 10000
                live_service = PortfolioService(self.project_root, context="live")
                l_eq, _, _ = live_service._get_journal_metrics()
                equity = l_eq if l_eq > 0 else 10000.0
            else:
                equity = 10000.0
        
        sum_invested = sum(p.market_value for p in positions if p.market_value is not None)
        
        # In paper mode, buying power should be equity - invested 
        # unless explicitly tracked otherwise in journal
        if self.context == "paper" and (cash <= 0 or cash == equity):
             cash = equity - sum_invested

        sum_unrealized_pl = sum(p.unrealized_pl for p in positions if p.unrealized_pl is not None)
        sum_initial_risk = sum(p.initial_risk for p in positions if p.initial_risk is not None)
        
        # New emoji based counting
        c_ok = sum(1 for p in positions if "🟢" in p.status_flags)
        c_warning = sum(1 for p in positions if "🟡" in p.status_flags or "⏳" in p.status_flags)
        c_danger = sum(1 for p in positions if "🔴" in p.status_flags or "⚠️" in p.status_flags)
        
        return PortfolioSummary(
            total_invested=sum_invested,
            total_unrealized_pl=sum_unrealized_pl,
            total_risk=sum_initial_risk,
            buying_power=cash,
            equity=equity,
            position_count=len(positions),
            count_ok=c_ok,
            count_warning=c_warning,
            count_danger=c_danger
        )

    def _save_risk_data(self, data: Dict):
        """Save risk data to JSON file."""
        with open(self.risk_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def update_paper_journal(self, equity: float, assets: float):
        """Saves current paper metrics to paper_journal.csv."""
        if self.context != "paper":
            return
            
        # Simplified record: date;equity;cash;assets
        # cash = equity - assets (approx)
        date_str = datetime.now().strftime("%Y-%m-%d")
        cash = equity - assets
        
        # Check if file exists to write header
        write_header = not os.path.exists(self.journal_file)
        
        with open(self.journal_file, 'a', encoding='utf-8') as f:
            if write_header:
                f.write("Date;Equity;Cash;Total_Assets\n")
            f.write(f"{date_str};{equity:.2f};{cash:.2f};{assets:.2f}\n")
            
    # --- Paper Trading Specific Methods ---
    
    def init_from_live(self):
        """Clones live trades.xml to paper-trades.xml and risk data."""
        if self.context != "paper":
            return
            
        import shutil
        live_trades = os.path.join(self.project_root, "trades.xml")
        live_risk = os.path.join(self.project_root, "manual_risk_data.json")
        
        if os.path.exists(live_trades):
            shutil.copy2(live_trades, self.trades_file)
        if os.path.exists(live_risk):
            shutil.copy2(live_risk, self.risk_file)
            
    def add_paper_position(self, symbol: str, entry_price: float, stop_loss: float, risk_pct: float = 1.0, quantity: Optional[float] = None) -> Dict:
        """
        Adds a simulated position to paper-trades.xml.
        If quantity is provided, it overrides risk-based sizing.
        Returns details about the created position.
        """
        if self.context != "paper":
            raise ValueError("Can only add paper positions in paper context")
            
        # 1. Get Live Equity
        equity, _, _ = self._get_journal_metrics()
        if equity <= 0: equity = 10000.0 # Fallback
        
        # 2. Calculate Sizing
        risk_amount = equity * (risk_pct / 100.0)
        risk_per_share = abs(entry_price - stop_loss)
        
        if quantity is not None and quantity > 0:
            qty = int(quantity)
            # Re-calculate implied risk amount for reporting
            risk_amount = qty * risk_per_share
        elif risk_per_share == 0:
            qty = 0
        else:
            qty = math.floor(risk_amount / risk_per_share)
            
        if qty <= 0:
            return {"error": "Quantity 0. Stop too close or risk too low."}
            
        # 3. Create Transaction XML Entry
        try:
            if os.path.exists(self.trades_file):
                tree = ET.parse(self.trades_file)
                root = tree.getroot()
            else:
                root = ET.Element("TradeLog")
                tree = ET.ElementTree(root)
            
            # Find or create <Trades> section
            trades_node = root.find("Trades")
            if trades_node is None:
                # Insert at the beginning of the root
                trades_node = ET.Element("Trades")
                root.insert(0, trades_node)
            
            # Create <Trade> node compatible with XmlInputParser
            trade_id = f"PAPER_{symbol}_{int(datetime.now().timestamp())}"
            trade_node = ET.SubElement(trades_node, "Trade", id=trade_id, isin=f"PAPER_{symbol}")
            
            meta_node = ET.SubElement(trade_node, "Meta")
            ET.SubElement(meta_node, "Date").text = datetime.now().strftime("%d.%m.%Y")
            ET.SubElement(meta_node, "Time").text = datetime.now().strftime("%H:%M:%S")
            
            instr_node = ET.SubElement(trade_node, "Instrument")
            ET.SubElement(instr_node, "Symbol").text = symbol
            # We assume currency from paper entry or default to EUR if not provided. 
            # In paper trade, we use USD as default for convenience or inherit from parent
            ET.SubElement(instr_node, "Currency").text = "USD" 
            
            exec_node = ET.SubElement(trade_node, "Execution")
            ET.SubElement(exec_node, "Quantity").text = str(qty).replace('.', ',')
            ET.SubElement(exec_node, "Price").text = str(entry_price).replace('.', ',')
            ET.SubElement(exec_node, "Commission").text = "0,00"
            ET.SubElement(exec_node, "Proceeds").text = str(-(qty * entry_price)).replace('.', ',')
            
            # Write back
            tree.write(self.trades_file, encoding="utf-8", xml_declaration=True)
            
        except Exception as e:
            return {"error": f"XML Error while saving PAPER trade: {str(e)}"}
                
        # 4. Set Stop Loss in Risk Data
        self.update_stop_loss(symbol, stop_loss)
        
        # 5. Auto-update paper_journal.csv to reflect new exposure
        invested = qty * entry_price
        _, _, old_assets = self._get_journal_metrics()
        new_assets = old_assets + invested
        self.update_paper_journal(equity, new_assets)
        
        return {
            "symbol": symbol,
            "qty": qty,
            "entry": entry_price,
            "stop": stop_loss,
            "invested": invested,
            "risk_amount": risk_amount,
            "risk_pct": risk_pct
        }

    def clear_paper_portfolio(self) -> bool:
        """Wipes all paper trades and paper risk data."""
        if self.context != "paper":
            return False
            
        try:
            # Reset XML
            root = ET.Element("TradeLog")
            ET.SubElement(root, "Trades")
            tree = ET.ElementTree(root)
            tree.write(self.trades_file, encoding="utf-8", xml_declaration=True)
            
            # Reset Risk Data
            self._save_risk_data({})
            
            # Reset journal to equity with 0 exposure
            equity, _, _ = self._get_journal_metrics()
            if equity > 0:
                self.update_paper_journal(equity, 0.0)
            
            return True
        except:
            return False

    def delete_paper_position(self, symbol: str) -> bool:
        """Removes a simulated position from paper-trades.xml."""
        if self.context != "paper" or not os.path.exists(self.trades_file):
            return False
            
        try:
            tree = ET.parse(self.trades_file)
            root = tree.getroot()
            trades_node = root.find("Trades")
            if trades_node is None: return False
            
            removed = False
            for t in trades_node.findall("Trade"):
                instr = t.find("Instrument/Symbol")
                if instr is not None and instr.text == symbol:
                    trades_node.remove(t)
                    removed = True
            
            if removed:
                tree.write(self.trades_file, encoding="utf-8", xml_declaration=True)
                # Also cleanup risk data
                self.delete_stop_loss(symbol)
                
                # Recalculate and update journal exposure
                # We need to get current total from remaining positions
                # Re-parse to get new total
                summary = self.get_summary()
                equity, _, _ = self._get_journal_metrics()
                self.update_paper_journal(equity, summary.total_invested)
                
                return True
        except:
            pass
        return False

    def update_paper_quantity(self, symbol: str, new_qty: float) -> bool:
        """Updates the quantity of a simulated position in paper-trades.xml."""
        if self.context != "paper" or not os.path.exists(self.trades_file):
            return False
            
        try:
            tree = ET.parse(self.trades_file)
            root = tree.getroot()
            trades_node = root.find("Trades")
            if trades_node is None: return False
            
            updated = False
            for t in trades_node.findall("Trade"):
                instr = t.find("Instrument/Symbol")
                if instr is not None and instr.text == symbol:
                    qty_node = t.find("Execution/Quantity")
                    if qty_node is not None:
                        qty_node.text = str(new_qty).replace('.', ',')
                        updated = True
            
            if updated:
                tree.write(self.trades_file, encoding="utf-8", xml_declaration=True)
                # Refresh risk calculation based on new quantity
                risk_data = self._load_risk_data()
                # Find the key (re-use stop loss logic if possible)
                pos_data = self.get_open_positions() # This builds the Objects
                for p in pos_data:
                    if p.symbol == symbol:
                        self.update_stop_loss(symbol, p.stop_loss)
                return True
        except:
            pass
        return False

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
