# -*- coding: utf-8 -*-
import argparse
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal, getcontext

# Set precision for Decimal calculations
getcontext().prec = 10

class MarketData:
    """Handles loading, caching, and providing market and FX data."""
    def __init__(self, data_path='./data/market/'):
        self.data_path = data_path
        self.asset_cache = {}
        self.fx_cache = {}
        print(f"-> MarketData initialized. Path: '{self.data_path}'")

    def _load_json(self, file_path):
        """Loads a JSON file from the specified path."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # print(f"Warning: Could not load or parse {file_path}. {e}")
            return None

    def get_asset_data(self, isin):
        """Retrieves asset data from cache or file."""
        if isin not in self.asset_cache:
            file_path = os.path.join(self.data_path, f"{isin}.json")
            self.asset_cache[isin] = self._load_json(file_path)
        return self.asset_cache[isin]

    def get_fx_data(self, pair):
        """Retrieves FX data from cache or file."""
        if pair not in self.fx_cache:
            file_path = os.path.join(self.data_path, f"{pair}.json")
            self.fx_cache[pair] = self._load_json(file_path)
        return self.fx_cache[pair]

    def get_market_price(self, isin, date):
        """Gets the closing price for an asset on a specific date, with fallback."""
        asset_data = self.get_asset_data(isin)
        if not asset_data or 'history' not in asset_data:
            return None
        
        # Search backwards from the given date for the most recent price
        current_date = date
        for _ in range(10): # Fallback up to 10 days
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str in asset_data['history']:
                return Decimal(str(asset_data['history'][date_str]['close']))
            current_date -= timedelta(days=1)
        return None

    def get_fx_rate(self, pair, date):
        """Gets the FX rate for a pair on a specific date, with fallback."""
        if pair[:3] == pair[3:]: # e.g., EUR to EUR is always 1
            return Decimal('1.0')
            
        fx_data = self.get_fx_data(pair)
        if not fx_data or 'history' not in fx_data:
            return None

        # Search backwards from the given date for the most recent rate
        current_date = date
        for _ in range(10): # Fallback up to 10 days
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str in fx_data['history']:
                return Decimal(str(fx_data['history'][date_str]))
            current_date -= timedelta(days=1)
        return None


class Position:
    """Represents a single position in the portfolio. (Data Container)"""
    def __init__(self, symbol, currency, isin):
        self.symbol = symbol
        self.currency = currency
        self.isin = isin
        self.quantity = Decimal('0')
        self.avg_entry_price = Decimal('0')
        self.invested_capital = Decimal('0') # In native currency
        self.invested_capital_eur = Decimal('0') # Cost-basis in EUR


class Portfolio:
    """Manages all positions and financial metrics."""
    def __init__(self, market_data):
        self.positions = {}  # symbol -> Position object
        self.cash_balance = {} # currency -> Decimal
        self.realized_pnl_eur = Decimal('0')
        self.dividends_eur = Decimal('0')
        self.inflow_eur = Decimal('0')
        self.market_data = market_data

    def get_position(self, symbol, currency, isin):
        """Retrieves or creates a position."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol, currency, isin)
        
        # [Fix] Update ISIN if it was missing in the initial creation but is present now
        if not self.positions[symbol].isin and isin:
            self.positions[symbol].isin = isin
            
        return self.positions[symbol]

    def _execute_trade(self, position, trade_quantity, trade_price, commission, trade_date, start_date):
        """
        Executes a trade, updating position state and calculating PnL.
        This method now contains all logic previously in Position.update.
        """
        # --- Get historical FX rate for this transaction ---
        fx_rate = self.market_data.get_fx_rate(f"{position.currency}EUR", trade_date)
        if not fx_rate:
            print(f"Warning: Could not find FX rate for {position.currency}EUR on {trade_date.strftime('%Y-%m-%d')}. Trade calculations may be inaccurate.")
            fx_rate = Decimal('1.0') # Fallback to 1 to avoid crashing

        # --- Logic for Buy/Increase or Sell/Reduce ---
        is_closing_trade = (position.quantity * trade_quantity) < 0
        is_opening_trade = (position.quantity * trade_quantity) >= 0

        if is_opening_trade:
            native_cost = (trade_quantity * trade_price) + commission
            eur_cost = native_cost * fx_rate
            
            position.invested_capital += native_cost
            position.invested_capital_eur += eur_cost
            position.quantity += trade_quantity
            
            if position.quantity != 0:
                position.avg_entry_price = abs(position.invested_capital / position.quantity)

        elif is_closing_trade:
            # --- 1. PnL Calculation ---
            if trade_date >= start_date:
                native_pnl = Decimal('0')
                if trade_quantity < 0: # Selling a long position
                    net_proceeds = (abs(trade_quantity) * trade_price) - commission
                    cost_basis_native = position.avg_entry_price * abs(trade_quantity)
                    native_pnl = net_proceeds - cost_basis_native
                else: # Covering a short position
                    cost_to_cover = (trade_quantity * trade_price) + commission
                    credit_from_short = position.avg_entry_price * trade_quantity
                    native_pnl = credit_from_short - cost_to_cover
                
                self.realized_pnl_eur += native_pnl * fx_rate

            # --- 2. Update Invested Capital ---
            # Reduce invested capital proportionally
            if position.invested_capital != 0:
                cost_basis_of_sold_shares = position.avg_entry_price * abs(trade_quantity)
                proportion_sold = cost_basis_of_sold_shares / position.invested_capital
                
                position.invested_capital_eur -= position.invested_capital_eur * proportion_sold
                position.invested_capital -= cost_basis_of_sold_shares

            position.quantity += trade_quantity

        # --- Cleanup for near-zero quantities ---
        if abs(position.quantity) < Decimal('1e-6'):
            position.quantity = Decimal('0')
            position.invested_capital = Decimal('0')
            position.invested_capital_eur = Decimal('0')
            position.avg_entry_price = Decimal('0')


    def process_trade(self, trade, trade_date, start_date):
        """Processes a single trade, handling flips, and updates the corresponding position."""
        symbol = trade.find('Instrument/Symbol').text
        currency = trade.find('Instrument/Currency').text
        isin = trade.get('isin') # Read ISIN from attribute

        # [Fix] Allow processing even if ISIN is missing (e.g. legacy imports)
        # if not isin:
        #    return
        
        quantity = Decimal(trade.find('Execution/Quantity').text.replace(',', '.'))
        price = Decimal(trade.find('Execution/Price').text.replace(',', '.'))
        proceeds = Decimal(trade.find('Execution/Proceeds').text.replace(',', '.'))
        commission = Decimal(trade.find('Execution/Commission').text.replace(',', '.'))

        position = self.get_position(symbol, currency, isin)

        # --- Update Physical Cash Balance (remains in native currency) ---
        self.cash_balance.setdefault(currency, Decimal('0'))
        self.cash_balance[currency] += proceeds

        # --- Handle Flip Trades (S-ALG-210) ---
        new_quantity = position.quantity + quantity
        is_flip = (position.quantity * new_quantity) < 0

        if is_flip:
            closing_quantity = -position.quantity
            ratio = abs(closing_quantity / quantity)
            closing_commission = commission * ratio
            self._execute_trade(position, closing_quantity, price, closing_commission, trade_date, start_date)

            opening_quantity = new_quantity
            opening_commission = commission - closing_commission
            self._execute_trade(position, opening_quantity, price, opening_commission, trade_date, start_date)
        else:
            self._execute_trade(position, quantity, price, commission, trade_date, start_date)

    def process_dividend(self, dividend, dividend_date, start_date):
        """Processes a dividend payment."""
        currency = dividend.find('Currency').text
        amount = Decimal(dividend.find('Amount').text.replace(',', '.'))
        self.cash_balance.setdefault(currency, Decimal('0'))
        self.cash_balance[currency] += amount

        if dividend_date >= start_date:
            fx_rate = self.market_data.get_fx_rate(f"{currency}EUR", dividend_date)
            if fx_rate:
                self.dividends_eur += amount * fx_rate
            else:
                print(f"Warning: Could not find FX rate for {currency}EUR on {dividend_date.strftime('%Y-%m-%d')}. Dividend not converted.")

    def process_deposit(self, transaction):
        """Processes a deposit or withdrawal and tracks EUR inflow."""
        currency = transaction.find('Currency').text
        amount = Decimal(transaction.find('Amount').text.replace(',', '.'))
        desc = transaction.find('Desc').text
        
        # Update physical cash balance for all transactions
        self.cash_balance.setdefault(currency, Decimal('0'))
        self.cash_balance[currency] += amount

        # ONLY include specific transfers in the theoretical inflow (S-ALG-230)
        if desc == 'Elektronischer Guthabentransfer':
            trans_date_str = transaction.find('Date').text
            trans_date = parse_xml_date(trans_date_str)
            fx_rate = self.market_data.get_fx_rate(f"{currency}EUR", trans_date)

            if fx_rate:
                self.inflow_eur += amount * fx_rate
            else:
                print(f"Warning: Could not find FX rate for Deposit in {currency} on {trans_date.strftime('%Y-%m-%d')}. Inflow not tracked.")


def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate a portfolio snapshot from a trades.xml file.")
    parser.add_argument('--end', 
                        default=datetime.now().strftime('%Y-%m-%d'),
                        help="End date for the snapshot (YYYY-MM-DD). Defaults to today.")
    parser.add_argument('--start', 
                        help="Start date for performance metrics (YYYY-MM-DD). Defaults to the first trade date if not provided.")
    parser.add_argument('--input', 
                        default='trades.xml',
                        help="Input XML file. Defaults to trades.xml.")
    return parser.parse_args()

def parse_xml_date(date_str):
    """Parses date from DD.MM.YYYY format."""
    return datetime.strptime(date_str, '%d.%m.%Y')

def _to_german_str(dec_val, precision=2):
    """Converts a Decimal to a German-style formatted string."""
    if not isinstance(dec_val, Decimal):
        dec_val = Decimal(str(dec_val))
    # Format to a string with a period decimal separator, then replace
    return f"{dec_val:,.{precision}f}".replace('.', '#').replace(',', '.').replace('#', ',')

def generate_xml_output(portfolio, start_date, end_date):
    """Generates the output XML file from the portfolio state."""
    
    output_filename = "portfolio.xml"
    market_data = portfolio.market_data

    # --- Delete existing file ---
    if os.path.exists(output_filename):
        try:
            os.remove(output_filename)
        except OSError as e:
            print(f"Error: Could not delete existing file '{output_filename}'.\n{e}")
            return

    # --- Pre-calculation and Aggregation ---
    total_asset_value_eur = Decimal('0')
    total_open_invested_eur = Decimal('0')

    # --- Positions Section ---
    positions_xml = ET.Element('Positions')
    for symbol, pos in sorted(portfolio.positions.items()):
        if abs(pos.quantity) < Decimal('1e-6'): # S-ALG-240
            continue

        pos_elem = ET.SubElement(positions_xml, 'Position')
        ET.SubElement(pos_elem, 'Symbol').text = pos.symbol
        ET.SubElement(pos_elem, 'Currency').text = pos.currency
        ET.SubElement(pos_elem, 'Quantity').text = _to_german_str(pos.quantity, precision=2)
        ET.SubElement(pos_elem, 'AvgEntryPrice').text = _to_german_str(pos.avg_entry_price, precision=4)
        
        # Add historical cost in EUR for reference/debugging
        ET.SubElement(pos_elem, 'InvestedCapital_EUR_Cost').text = _to_german_str(pos.invested_capital_eur)

        # Fetch market data for the position
        market_price_native = market_data.get_market_price(pos.isin, end_date)
        
        if market_price_native:
            # --- Daily PnL Calculation (S-ALG-260) ---
            price_prev_day = market_data.get_market_price(pos.isin, end_date - timedelta(days=1))
            daily_pnl_native = Decimal('0')
            if price_prev_day:
                daily_pnl_native = (market_price_native - price_prev_day) * pos.quantity

            market_value_native = pos.quantity * market_price_native
            unrealized_pnl_native = market_value_native - pos.invested_capital

            ET.SubElement(pos_elem, 'MarketPrice').text = _to_german_str(market_price_native, precision=4)
            ET.SubElement(pos_elem, 'MarketValue').text = _to_german_str(market_value_native, precision=2)
            ET.SubElement(pos_elem, 'UnrealizedPnL').text = _to_german_str(unrealized_pnl_native, precision=2)
            ET.SubElement(pos_elem, 'DailyPnL').text = _to_german_str(daily_pnl_native, precision=2)

            # Convert to EUR for summary aggregation (F-300)
            fx_rate_end_date = market_data.get_fx_rate(f"{pos.currency}EUR", end_date)
            if fx_rate_end_date:
                total_asset_value_eur += market_value_native * fx_rate_end_date
                total_open_invested_eur += pos.invested_capital_eur # Sum for theoretical cash
            else:
                 print(f"Warning: Could not find FX rate for {pos.currency}EUR on {end_date.strftime('%Y-%m-%d')}. Position {pos.symbol} not included in EUR summary.")
        else:
            print(f"Warning: Could not find market price for {pos.symbol} ({pos.isin}) on {end_date.strftime('%Y-%m-%d')}.")

    # --- Summary Section ---
    summary = ET.Element('Summary')
    
    # Report Parameters
    params = ET.SubElement(summary, 'ReportParams')
    ET.SubElement(params, 'StartDate').text = start_date.strftime('%Y-%m-%d') if start_date else "None"
    ET.SubElement(params, 'EndDate').text = end_date.strftime('%Y-%m-%d')

    # Aggregated EUR Metrics (F-260 & S-ALG-230)
    theoretical_cash_eur = portfolio.inflow_eur + portfolio.realized_pnl_eur - total_open_invested_eur
    total_portfolio_value_eur = total_asset_value_eur + theoretical_cash_eur
    
    ET.SubElement(summary, 'AssetValue').text = _to_german_str(total_asset_value_eur)
    ET.SubElement(summary, 'CashValue').text = _to_german_str(theoretical_cash_eur) # Using Theoretical Cash
    ET.SubElement(summary, 'TotalPortfolioValue').text = _to_german_str(total_portfolio_value_eur)
    ET.SubElement(summary, 'Inflow').text = _to_german_str(portfolio.inflow_eur)


    # --- Period Metrics Section ---
    period_metrics = ET.SubElement(summary, 'PeriodMetrics')
    
    # Realized PnL (already in EUR)
    pnl_elem = ET.SubElement(period_metrics, 'RealizedPnL')
    pnl_elem.set('currency', 'EUR')
    pnl_elem.text = _to_german_str(portfolio.realized_pnl_eur)

    # Dividends (already in EUR)
    dividend_elem = ET.SubElement(period_metrics, 'Dividends')
    dividend_elem.set('currency', 'EUR')
    dividend_elem.text = _to_german_str(portfolio.dividends_eur)


    # --- Construct Final XML ---
    root = ET.Element('Portfolio')
    root.append(summary)
    root.append(positions_xml)

    # --- Write to file ---
    # Pretty print using lxml if available, otherwise use standard xml
    try:
        from lxml import etree
        xml_string = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8')
    except ImportError:
        xml_string = ET.tostring(root, encoding='utf-8')

    with open(output_filename, 'wb') as f:
        f.write(xml_string)
    
    print(f"Successfully generated portfolio snapshot: {output_filename}")


def main():
    """Main function to run the portfolio generator."""
    args = parse_arguments()
    
    end_date = datetime.strptime(args.end, '%Y-%m-%d')
    
    try:
        tree = ET.parse(args.input)
        root = tree.getroot()
    except (FileNotFoundError, ET.ParseError) as e:
        print(f"Error: Could not read or parse the input file '{args.input}'.\n{e}")
        return

    market_data = MarketData()
    portfolio = Portfolio(market_data)
    
    all_trades = root.findall('.//Trade')
    if not all_trades:
        print("No trades found in the input file.")
        return
        
    sorted_trades = sorted(all_trades, key=lambda t: parse_xml_date(t.find('Meta/Date').text))

    # Set start_date default
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        first_trade_date_str = sorted_trades[0].find('Meta/Date').text
        start_date = parse_xml_date(first_trade_date_str)


    for trade in sorted_trades:
        trade_date_str = trade.find('Meta/Date').text
        trade_date = parse_xml_date(trade_date_str)
        
        if trade_date <= end_date:
            portfolio.process_trade(trade, trade_date, start_date)
    
    # Process Dividends
    for dividend in root.findall('.//Dividend'):
        date_node = dividend.find('Date')
        if date_node is not None and date_node.text:
            dividend_date = parse_xml_date(date_node.text)
            if dividend_date <= end_date:
                portfolio.process_dividend(dividend, dividend_date, start_date)

    # Process Deposits/Withdrawals
    for deposit in root.findall('.//DepositsWithdrawals/Transaction'):
        if parse_xml_date(deposit.find('Date').text) <= end_date:
            portfolio.process_deposit(deposit)

    # --- Generate XML Output ---
    generate_xml_output(portfolio, start_date, end_date)


if __name__ == "__main__":
    main()
