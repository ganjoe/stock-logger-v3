import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional
import logging
from .domain import IXmlParser, TradeEvent, CashEvent, DividendEvent, TransactionType

class XmlInputParser(IXmlParser):
    def _parse_decimal(self, val_str: str) -> Decimal:
        """ 
        Handles German format '1.200,50' -> '1200.50'
        Also handles standard format '1200.50' gracefully if mixed?
        Spec F-DATA-010 is explicit about German format.
        """
        if not val_str: return Decimal("0")
        # Remove dots (thousands s.) and replace comma with dot
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

    def parse_trades(self, filepath: str) -> List[TradeEvent]:
        events = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Xpath might vary depending on namespace or structure.
            # Assuming <TradeLog><Trades><Trade ...>
            trades = root.find("Trades")
            if trades is None: 
                logging.warning("No <Trades> section found")
                return []
                
            for t in trades.findall("Trade"):
                try:
                    # Parse Quantity first to determine Type
                    qty_elem = t.find("Execution/Quantity")
                    if qty_elem is None:
                        logging.warning(f"Trade {t.get('id')} has no Quantity")
                        continue
                        
                    raw_qty = self._parse_decimal(qty_elem.text)
                    
                    if raw_qty > 0:
                        type = TransactionType.BUY
                        quantity = raw_qty
                    else:
                        type = TransactionType.SELL
                        quantity = abs(raw_qty)
                        
                    # Meta Tags
                    meta = t.find("Meta")
                    date_str = meta.find("Date").text if meta is not None else "01.01.1970"
                    time_str = meta.find("Time").text if meta is not None else "00:00:00"
                    
                    # Instrument tags
                    instr = t.find("Instrument")
                    symbol = instr.find("Symbol").text if instr is not None else "UNK"
                    isin = t.get("isin", "") # Attribute on Trade tag
                    currency = instr.find("Currency").text if instr is not None else "EUR"
                    
                    # Execution tags
                    exec_sec = t.find("Execution")
                    price = self._parse_decimal(exec_sec.find("Price").text)
                    comm_elem = exec_sec.find("Commission")
                    comm_val = self._parse_decimal(comm_elem.text) if comm_elem is not None else Decimal("0")
                    
                    # Parse ID from attribute
                    trade_id = t.get("id", "unk")

                    events.append(TradeEvent(
                        id=trade_id,
                        date=self._parse_date(date_str),
                        time=time_str,
                        symbol=symbol,
                        isin=isin,
                        type=type,
                        quantity=quantity,
                        price=price,
                        commission=comm_val,
                        currency=currency
                    ))
                except Exception as e:
                    logging.error(f"Error parsing trade: {e}")
            
        except ET.ParseError as e:
            logging.error(f"XML Parse Error: {e}")
        
        return events

    def parse_cash(self, filepath: str) -> List[CashEvent]:
        events = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            section = root.find("DepositsWithdrawals")
            if section is None: return []

            # Handle Transactions (Deposits/Withdrawals)
            for t in section.findall("Transaction"):
                try:
                    amount = self._parse_decimal(t.find("Amount").text)
                    currency = t.find("Currency").text
                    date_val = self._parse_date(t.find("Date").text)
                    
                    if amount >= 0:
                        events.append(CashEvent(
                            id=t.get("id", "unk"),
                            date=date_val,
                            type=TransactionType.DEPOSIT,
                            amount=amount,
                            currency=currency
                        ))
                    else:
                        events.append(CashEvent(
                            id=t.get("id", "unk"),
                            date=date_val,
                            type=TransactionType.WITHDRAWAL,
                            amount=abs(amount),
                            currency=currency
                        ))
                except Exception as e:
                    logging.error(f"Error parsing cash transaction: {e}")

        except:
            pass
        return events

    def parse_dividends(self, filepath: str) -> List[DividendEvent]:
        events = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            section = root.find("Dividends")
            if section is None: return []
            
            for d in section.findall("Dividend"):
                events.append(DividendEvent(
                    id=d.get("id", "unk"),
                    date=self._parse_date(d.get("date")),
                    symbol=d.get("symbol", ""),
                    isin=d.get("isin", ""),
                    amount=self._parse_decimal(d.get("amount")),
                    currency=d.get("currency", "EUR")
                ))
        except:
            pass
        return events
