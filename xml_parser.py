
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import logging
from alm_types import RawEvent, TransactionType

class TradeLogParser:
    def parse_file(self, file_path: str) -> List[RawEvent]:
        """ Parses XML and creates chronological RawEvents. """
        events: List[RawEvent] = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logging.error(f"Failed to parse XML file {file_path}: {e}")
            return []

        # The structure can be <TradeLog> -> many numbered children <1>, <2>...
        # We need to sort them numerically by tag to ensure chronology if they are not already.
        
        # Filter strictly for numeric tags to avoid parsing <Trades> or <DepositsWithdrawals> container tags if they exist as noise
        # Wait, requirements say: "Root <TradeLog> contains directly numbered child elements... OR <Trades>/<DepositsWithdrawals>?"
        # Correction based on user input for trades-test.xml rewrite: 
        # The user forced a structure update to: <TradeLog><Trades><Trade>...</Trades><DepositsWithdrawals><Transaction>...</Transaction></DepositsWithdrawals>
        # BUT the CSV requirements F-XML-010 say: "Direct numbered child elements <1>, <2>".
        # CONFLICT RESOLUTION: "trades-test.xml" was rewritten to standard schema, but F-XML-010 says numbered elements.
        # However, the user said "trades-test.xml" matches "trades.xml".
        # Looking at original `trades.xml` view (Step 52/56), it showed <TradeLog><Trades><Trade id="..."></Trade>...</Trades>
        # AND Step 146 showed <DepositsWithdrawals><Transaction>...</Transaction>
        # SO the requirement F-XML-010 "pure numbered elements" seems to be from an OLDER brainstorming version or misunderstanding.
        # REALITY defined by FILE CONTENT: We must parse <Trades>/<Trade> and <DepositsWithdrawals>/<Transaction>.
        # We will flatten these into a list and sort by Date/Time because IDs are not sequential integers in the real file (hashes).
        
        # Update strategy: Parse all Trades and Transactions, then sort by timestamp.
        
        # 1. Parse Trades
        trades_node = root.find('Trades')
        if trades_node is not None:
            for trade in trades_node.findall('Trade'):
                try:
                    ev = self._parse_trade_element(trade)
                    if ev:
                        events.append(ev)
                except Exception as e:
                    logging.warning(f"Error parsing trade: {e}")

        # 2. Parse Deposits/Withdrawals
        dw_node = root.find('DepositsWithdrawals')
        if dw_node is not None:
            for trans in dw_node.findall('Transaction'):
                try:
                    ev = self._parse_transaction_element(trans)
                    if ev:
                        events.append(ev)
                except Exception as e:
                    logging.warning(f"Error parsing transaction: {e}")
                    
        # 3. Parse Dividends (Assuming separate root container or sibling)
        # Based on snippet: <Dividend id="...">
        # It seems Dividend elements are just children of TradeLog or similar container. 
        # Check if they are direct children or wrapped.
        # User snippet showed indented: <Dividend>.
        # We will try 'Dividend' search on Root and recursively just in case.
        # Strict requirement: "Root <TradeLog>... <Dividend>"
        
        div_list = root.findall('Dividend')
        if not div_list:
            # Maybe inside a Dividends container?
            divs_node = root.find('Dividends')
            if divs_node is not None:
                div_list = divs_node.findall('Dividend')
                
        for div in div_list:
            try:
                ev = self._parse_dividend_element(div)
                if ev:
                    events.append(ev)
            except Exception as e:
                logging.warning(f"Error parsing dividend: {e}")

        # 4. Sort by Timestamp
        events.sort(key=lambda x: x.timestamp)
        
        return events

    def _parse_dividend_element(self, elem: ET.Element) -> Optional[RawEvent]:
        date_str = elem.findtext('Date', '')
        # Dividend often has no time, assume EOD or check if Time tag exists
        time_str = elem.findtext('Time', '00:00:00')
        ts = self._parse_datetime(date_str, time_str)
        
        event_id = elem.get('id', 'unknown')
        symbol = elem.findtext('Symbol')
        amount_str = elem.findtext('Amount', '0')
        currency = elem.findtext('Currency', 'EUR')
        
        amount = self._parse_german_decimal(amount_str)
        
        return RawEvent(
            event_id=event_id,
            timestamp=ts,
            type=TransactionType.DIVIDEND,
            symbol=symbol,
            amount=amount,
            currency=currency
        )

    def _parse_trade_element(self, elem: ET.Element) -> Optional[RawEvent]:
        # Meta
        meta = elem.find('Meta')
        if meta is None: return None
        
        date_str = meta.findtext('Date', '')
        time_str = meta.findtext('Time', '')
        ts = self._parse_datetime(date_str, time_str)
        
        # ID from attribute or tag? Real trades.xml uses id attribute
        event_id = elem.get('id', 'unknown')
        
        # Instrument
        instr = elem.find('Instrument')
        symbol = instr.findtext('Symbol') if instr is not None else None
        currency = instr.findtext('Currency', 'EUR') if instr is not None else 'EUR'
        
        # Execution
        exe = elem.find('Execution')
        if exe is None: return None
        
        qty_str = exe.findtext('Quantity', '0')
        price_str = exe.findtext('Price', '0')
        comm_str = exe.findtext('Commission', '0')
        proc_str = exe.findtext('Proceeds', '0')
        
        qty = self._parse_german_decimal(qty_str)
        price = self._parse_german_decimal(price_str)
        comm = self._parse_german_decimal(comm_str)
        proc = self._parse_german_decimal(proc_str)
        
        # Determine Type
        # Qty > 0 -> BUY/COVER, Qty < 0 -> SELL/SHORT
        trans_type = TransactionType.BUY if qty > 0 else TransactionType.SELL
        
        return RawEvent(
            event_id=event_id,
            timestamp=ts,
            type=trans_type,
            symbol=symbol,
            currency=currency,
            quantity=qty,
            price=price,
            commission=comm,
            proceeds=proc
        )

    def _parse_transaction_element(self, elem: ET.Element) -> Optional[RawEvent]:
        date_str = elem.findtext('Date', '')
        # Transactions might not have time, assume 00:00:00 or try to parse
        # Original file didn't show timestamps for Transactions, assume EOD or start
        ts = self._parse_datetime(date_str, "00:00:00")
        
        event_id = elem.get('id', 'unknown')
        
        amount_str = elem.findtext('Amount', '0')
        currency = elem.findtext('Currency', 'EUR')
        
        amount = self._parse_german_decimal(amount_str)
        
        # Determine Type
        trans_type = TransactionType.INFLOW if amount > 0 else TransactionType.OUTFLOW
        
        return RawEvent(
            event_id=event_id,
            timestamp=ts,
            type=trans_type,
            amount=amount,
            currency=currency
        )
        
    def _parse_german_decimal(self, val: str) -> Decimal:
        """ Helper: '1.234,56' -> Decimal('1234.56') """
        if not val: return Decimal("0")
        clean = val.replace('.', '').replace(',', '.')
        try:
            return Decimal(clean)
        except:
            return Decimal("0")

    def _parse_datetime(self, d: str, t: str) -> datetime:
        try:
            dt_str = f"{d} {t}".strip()
            return datetime.strptime(dt_str, "%d.%m.%Y %H:%M:%S")
        except ValueError:
            # Fallback for missing seconds or malformed
            try:
                return datetime.strptime(d, "%d.%m.%Y")
            except:
                return datetime.min
