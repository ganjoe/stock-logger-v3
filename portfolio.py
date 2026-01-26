# -*- coding: utf-8 -*-
import argparse
import xml.etree.ElementTree as ET
import os
from datetime import datetime
from decimal import Decimal, getcontext

# Set precision for Decimal calculations
getcontext().prec = 10

class Position:
    """Represents a single position in the portfolio."""
    def __init__(self, symbol, currency):
        self.symbol = symbol
        self.currency = currency
        self.quantity = Decimal('0')
        self.avg_entry_price = Decimal('0')
        self.invested_capital = Decimal('0')

    def update(self, trade_quantity, trade_price, commission):
        """Updates the position attributes based on a new trade."""
        trade_quantity = Decimal(trade_quantity)
        trade_price = Decimal(trade_price)
        commission = Decimal(commission)

        # For buys/increasing a position
        if (self.quantity * trade_quantity) >= 0:
            # Add commission to the cost of a buy, or subtract from proceeds of a short sale
            total_cost = (trade_quantity * trade_price) + commission if trade_quantity > 0 else (trade_quantity * trade_price) - commission
            new_invested_capital = self.invested_capital + total_cost
            self.quantity += trade_quantity
            if self.quantity != 0:
                self.avg_entry_price = abs(new_invested_capital / self.quantity)
            self.invested_capital = new_invested_capital
        # For sells/reducing a position
        else:
            # Reduce invested capital by the cost basis of the sold shares
            self.invested_capital -= self.avg_entry_price * abs(trade_quantity)
            self.quantity += trade_quantity

        # If quantity is near zero, clean up
        if abs(self.quantity) < Decimal('1e-6'):
            self.quantity = Decimal('0')
            self.invested_capital = Decimal('0')
            self.avg_entry_price = Decimal('0')

class Portfolio:
    """Manages all positions and financial metrics."""
    def __init__(self):
        self.positions = {}  # symbol -> Position object
        self.cash_balance = {} # currency -> Decimal
        self.realized_pnl = {} # currency -> Decimal
        self.dividends = {} # currency -> Decimal

    def get_position(self, symbol, currency):
        """Retrieves or creates a position."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol, currency)
        return self.positions[symbol]

    def _execute_trade(self, position, trade_quantity, trade_price, commission, trade_date, start_date):
        """Executes a single, non-flip trade, calculating PnL and updating the position."""
        trade_quantity = Decimal(trade_quantity)
        trade_price = Decimal(trade_price)
        commission = Decimal(commission)
        
        # --- PnL Calculation (for closing trades) ---
        is_closing = (position.quantity * trade_quantity) < 0
        if is_closing and trade_date >= start_date:
            pnl = Decimal('0')
            # For selling a long position
            if trade_quantity < 0:
                net_proceeds = (abs(trade_quantity) * trade_price) - commission
                cost_basis = position.avg_entry_price * abs(trade_quantity)
                pnl = net_proceeds - cost_basis
            # For covering a short position
            else:
                cost_to_cover = (trade_quantity * trade_price) + commission
                credit_from_short = position.avg_entry_price * trade_quantity
                pnl = credit_from_short - cost_to_cover
            
            self.realized_pnl.setdefault(position.currency, Decimal('0'))
            self.realized_pnl[position.currency] += pnl
            
        # --- Update Position State ---
        position.update(trade_quantity, trade_price, commission)

    def process_trade(self, trade, trade_date, start_date):
        """Processes a single trade, handling flips, and updates the corresponding position."""
        symbol = trade.find('Instrument/Symbol').text
        currency = trade.find('Instrument/Currency').text
        
        # German locale string to Decimal conversion
        quantity_str = trade.find('Execution/Quantity').text.replace(',', '.')
        price_str = trade.find('Execution/Price').text.replace(',', '.')
        proceeds_str = trade.find('Execution/Proceeds').text.replace(',', '.')
        commission_str = trade.find('Execution/Commission').text.replace(',', '.')

        quantity = Decimal(quantity_str)
        price = Decimal(price_str)
        proceeds = Decimal(proceeds_str)
        commission = Decimal(commission_str)

        position = self.get_position(symbol, currency)

        # --- Update Cash Balance ---
        self.cash_balance.setdefault(currency, Decimal('0'))
        self.cash_balance[currency] += proceeds

        # --- Handle Flip Trades (S-ALG-210) ---
        new_quantity = position.quantity + quantity
        is_flip = (position.quantity * new_quantity) < 0

        if is_flip:
            # 1. Trade to close the position to zero
            closing_quantity = -position.quantity
            ratio = abs(closing_quantity / quantity)
            closing_commission = commission * ratio
            self._execute_trade(position, closing_quantity, price, closing_commission, trade_date, start_date)

            # 2. Trade to open the new position
            opening_quantity = quantity - closing_quantity
            opening_commission = commission - closing_commission
            self._execute_trade(position, opening_quantity, price, opening_commission, trade_date, start_date)
        else:
            # Process as a single, simple trade
            self._execute_trade(position, quantity, price, commission, trade_date, start_date)

    def process_dividend(self, dividend, dividend_date, start_date):
        """Processes a dividend payment."""
        currency = dividend.find('Currency').text
        amount = Decimal(dividend.find('Amount').text.replace(',', '.'))
        self.cash_balance.setdefault(currency, Decimal('0'))
        self.cash_balance[currency] += amount

        if dividend_date >= start_date:
            self.dividends.setdefault(currency, Decimal('0'))
            self.dividends[currency] += amount

    def process_deposit(self, transaction):
        """Processes a deposit or withdrawal."""
        currency = transaction.find('Currency').text
        amount = Decimal(transaction.find('Amount').text.replace(',', '.'))
        self.cash_balance.setdefault(currency, Decimal('0'))
        self.cash_balance[currency] += amount


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

def generate_xml_output(portfolio, start_date, end_date):
    """Generates the output XML file from the portfolio state."""
    
    output_filename = "portfolio.xml"

    # --- Delete existing file ---
    if os.path.exists(output_filename):
        try:
            os.remove(output_filename)
        except OSError as e:
            print(f"Error: Could not delete existing file '{output_filename}'.\n{e}")
            return

    # Create root element
    root = ET.Element('Portfolio')
    
    # --- Summary Section ---
    summary = ET.SubElement(root, 'Summary')
    
    # Report Parameters
    params = ET.SubElement(summary, 'ReportParams')
    ET.SubElement(params, 'StartDate').text = start_date.strftime('%Y-%m-%d') if start_date else "None"
    ET.SubElement(params, 'EndDate').text = end_date.strftime('%Y-%m-%d')
    
    # Cash Balances
    cash_balances = ET.SubElement(summary, 'CashBalances')
    for currency, balance in sorted(portfolio.cash_balance.items()):
        cash_elem = ET.SubElement(cash_balances, 'Cash')
        cash_elem.set('currency', currency)
        cash_elem.text = f"{balance:,.2f}".replace('.', ';').replace(',', '.').replace(';', ',')

    # --- Period Metrics Section ---
    period_metrics = ET.SubElement(summary, 'PeriodMetrics')
    
    # Realized PnL
    realized_pnl_xml = ET.SubElement(period_metrics, 'RealizedPnL')
    for currency, pnl in sorted(portfolio.realized_pnl.items()):
        pnl_elem = ET.SubElement(realized_pnl_xml, 'PnL')
        pnl_elem.set('currency', currency)
        pnl_elem.text = f"{pnl:,.2f}".replace('.', ';').replace(',', '.').replace(';', ',')

    # Dividends
    dividends_xml = ET.SubElement(period_metrics, 'Dividends')
    for currency, dividend_total in sorted(portfolio.dividends.items()):
        dividend_elem = ET.SubElement(dividends_xml, 'Dividend')
        dividend_elem.set('currency', currency)
        dividend_elem.text = f"{dividend_total:,.2f}".replace('.', ';').replace(',', '.').replace(';', ',')



    # --- Positions Section ---
    positions_xml = ET.SubElement(root, 'Positions')
    total_invested_capital = Decimal('0')
    
    for symbol, pos in sorted(portfolio.positions.items()):
        if pos.quantity != 0: # Requirement S-ALG-240
            pos_elem = ET.SubElement(positions_xml, 'Position')
            ET.SubElement(pos_elem, 'Symbol').text = pos.symbol
            ET.SubElement(pos_elem, 'Currency').text = pos.currency
            ET.SubElement(pos_elem, 'Quantity').text = f"{pos.quantity:.2f}".replace('.', ',')
            ET.SubElement(pos_elem, 'AvgEntryPrice').text = f"{pos.avg_entry_price:.4f}".replace('.', ',')
            
            invested_capital = pos.quantity * pos.avg_entry_price
            ET.SubElement(pos_elem, 'InvestedCapital').text = f"{invested_capital:.2f}".replace('.', ',')

            # Aggregate total invested capital (for summary)
            # Note: This is a simplification. Real calculation needs currency conversion.
            if pos.currency == 'USD': # Assuming USD is the primary currency for now
                 total_invested_capital += invested_capital

    # Add total invested capital to summary
    ET.SubElement(summary, 'TotalInvestedCapital').text = f"{total_invested_capital:.2f}".replace('.', ',')
    ET.SubElement(summary, 'TotalPortfolioRisk').text = f"{total_invested_capital:.2f}".replace('.', ',') # Placeholder per S-ALG-250


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

    portfolio = Portfolio()
    
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
