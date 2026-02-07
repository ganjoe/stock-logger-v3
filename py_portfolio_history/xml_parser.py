import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import datetime, date, time
from typing import List
import logging

from .types import Transaction

class XmlInputParser:
    def _parse_decimal(self, val_str: str) -> Decimal:
        """ Handles German format '1.200,50' -> '1200.50' """
        if not val_str: return Decimal("0")
        clean = val_str.replace('.', '').replace(',', '.')
        try:
            return Decimal(clean)
        except:
            return Decimal("0")
            
    def _parse_date(self, date_str: str) -> date:
        """ DD.MM.YYYY """
        try:
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            logging.warning(f"Invalid date {date_str}, using 1970-01-01")
            return date(1970, 1, 1)

    def parse_all(self, filepath: str) -> List[Transaction]:
        """ Helper to parse all types and return a single list """
        events = []
        events.extend(self.parse_trades(filepath))
        events.extend(self.parse_cash(filepath))
        events.extend(self.parse_dividends(filepath))
        return events

    def parse_trades(self, filepath: str) -> List[Transaction]:
        events = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            trades = root.find("Trades")
            if trades is None: return []

            for t in trades.findall("Trade"):
                try:
                    qty_elem = t.find("Execution/Quantity")
                    if qty_elem is None: continue
                    raw_qty = self._parse_decimal(qty_elem.text)
                    
                    if raw_qty > 0:
                        t_type = "BUY"
                        quantity = raw_qty
                    else:
                        t_type = "SELL"
                        quantity = abs(raw_qty)
                        
                    meta = t.find("Meta")
                    date_str = meta.find("Date").text if meta is not None else "01.01.1970"
                    time_str = meta.find("Time").text if meta is not None else "00:00:00"
                    
                    date_val = self._parse_date(date_str)
                    try:
                        time_val = datetime.strptime(time_str, "%H:%M:%S").time()
                    except:
                        time_val = time(0,0,0)
                        
                    full_date = datetime.combine(date_val, time_val)
                    
                    instr = t.find("Instrument")
                    symbol = instr.find("Symbol").text if instr is not None else "UNK"
                    # Default ISIN to empty string if missing? Or derive?
                    # F-DATA-020: Read from Attr, default ""
                    isin = t.get("isin", "")
                    currency = instr.find("Currency").text if instr is not None else "EUR"
                    
                    exec_sec = t.find("Execution")
                    price = self._parse_decimal(exec_sec.find("Price").text)
                    comm_elem = exec_sec.find("Commission")
                    comm_val = self._parse_decimal(comm_elem.text) if comm_elem is not None else Decimal("0")
                    # Fees in XML are often negative. We want positive magnitude for the calc logic?
                    # F-DATA-050: "als negative Werte (Kosten) interpretiert".
                    # My calculator logic adds fees if they are positive cost?
                    # Let's verify calculator logic.
                    # Calculator: "total_value_eur + fees_eur" for Buy (Cash Out).
                    # If XML has -5.00, then + (-5) is subtraction. That's wrong for "Total Cost = Price + Fees".
                    # Total Cost (Cash Outflow) = Stocks + Fees.
                    # If Fees are -5, we should ADD 5 to outflow.
                    # So we need ABS(fees) if they represent cost.
                    # Let's standardize: Calculator expects POSITIVE fee magnitude representing COST.
                    comm_val = abs(comm_val)

                    events.append(Transaction(
                        id=t.get("id", "unk"),
                        date=full_date,
                        type=t_type,
                        symbol=symbol,
                        isin=isin,
                        quantity=quantity,
                        price=price,
                        commission=comm_val,
                        currency=currency
                    ))
                except Exception as e:
                    logging.error(f"Error parsing trade: {e}")
        except:
             pass
        return events

    def parse_cash(self, filepath: str) -> List[Transaction]:
        events = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            section = root.find("DepositsWithdrawals")
            if section is None: return []

            for t in section.findall("Transaction"):
                try:
                    amount = self._parse_decimal(t.find("Amount").text)
                    currency = t.find("Currency").text
                    date_val = self._parse_date(t.find("Date").text)
                    full_date = datetime.combine(date_val, time(0,0,0))
                    
                    if amount >= 0:
                        t_type = "DEPOSIT"
                        qty = amount
                    else:
                        t_type = "WITHDRAWAL"
                        qty = abs(amount)
                        
                    events.append(Transaction(
                        id=t.get("id", "unk"),
                        date=full_date,
                        type=t_type,
                        symbol="", # Cash has no symbol
                        isin="",
                        quantity=qty, # Amount stored in quantity
                        price=Decimal("1.0"), 
                        commission=Decimal("0"),
                        currency=currency
                    ))
                except Exception as e:
                    logging.error(f"Error parsing cash: {e}")
        except:
             pass
        return events

    def parse_dividends(self, filepath: str) -> List[Transaction]:
        events = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            section = root.find("Dividends")
            if section is None: return []
            
            for d in section.findall("Dividend"):
                date_val = self._parse_date(d.get("date"))
                full_date = datetime.combine(date_val, time(0,0,0))
                
                events.append(Transaction(
                    id=d.get("id", "unk"),
                    date=full_date,
                    type="DIVIDEND",
                    symbol=d.get("symbol", ""),
                    isin=d.get("isin", ""),
                    quantity=self._parse_decimal(d.get("amount")), # Amount in Qty
                    price=Decimal("1.0"),
                    commission=Decimal("0"),
                    currency=d.get("currency", "EUR")
                ))
        except:
             pass
        return events
