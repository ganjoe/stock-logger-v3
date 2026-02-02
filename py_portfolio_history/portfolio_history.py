import sys
import argparse
import logging
from datetime import date, timedelta, datetime
from .domain import TransactionType
from .market_data import MarketDataManager
from .xml_parser import XmlInputParser
from .fifo_engine import FifoEngine
from .calculator import PortfolioCalculator
from .xml_generator import XmlOutputGenerator

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    parser = argparse.ArgumentParser(description="Portfolio History Analyzer")
    parser.add_argument("--input", default="trades.xml", help="Input XML file (default: trades.xml)")
    parser.add_argument("--output", default="portfolio-history.xml", help="Output XML file (default: portfolio-history.xml)")
    args = parser.parse_args()

    logging.info("Starting Portfolio History Analysis...")
    
    # 1. Components
    market_data = MarketDataManager("./data/market")
    xml_parser = XmlInputParser()
    fifo_engine = FifoEngine()
    calculator = PortfolioCalculator(market_data)
    xml_gen = XmlOutputGenerator()

    # 2. Parse Input
    logging.info(f"Parsing input: {args.input}")
    trades = xml_parser.parse_trades(args.input)
    cash = xml_parser.parse_cash(args.input)
    divs = xml_parser.parse_dividends(args.input)
    
    # 3. Sort Events Timeline
    # We need to process day by day.
    # Collect all unique dates
    all_dates = set()
    all_dates.update(t.date for t in trades)
    all_dates.update(c.date for c in cash)
    all_dates.update(d.date for d in divs)
    
    if not all_dates:
        logging.warning("No events found.")
        return

    sorted_dates = sorted(list(all_dates))
    start_date = sorted_dates[0]
    end_date = sorted_dates[-1] 
    
    # Combined Event list
    all_events = []
    for t in trades: all_events.append(t)
    for c in cash: all_events.append(c)
    for d in divs: all_events.append(d)
    
    # Sort by Date and Time
    # TradeEvent has 'time', others default to start of day or specific logic?
    # Helper to get sort key
    def get_sort_key(e):
        d = e.date
        t_str = "00:00:00"
        if hasattr(e, 'time'):
            t_str = e.time
        return datetime.combine(d, datetime.strptime(t_str, "%H:%M:%S").time())

    all_events.sort(key=get_sort_key)
    
    event_snapshots = []
    
    
    for event in all_events:
        # Robust Instance Check by type name
        type_name = type(event).__name__
        es = None
        
        if type_name == "TradeEvent":
             fifo_engine.process_trade(event)
             es = calculator.process_trade(event, fifo_engine)
        elif type_name == "CashEvent":
             es = calculator.process_cash(event, fifo_engine)
        elif type_name == "DividendEvent":
             es = calculator.process_dividend(event, fifo_engine)
             
        if es:
            event_snapshots.append(es)
        
    # 4. Generate Output
    logging.info("Calculating metrics...")
    metrics = calculator.calculate_metrics(fifo_engine.closed_trades, fifo_engine)
    
    logging.info("Generating XML...")
    xml_str = xml_gen.generate(event_snapshots, metrics)
    
    with open(args.output, "w", encoding='utf-8') as f:
        f.write(xml_str)
        
    logging.info(f"Done. Output written to {args.output}")

if __name__ == "__main__":
    main()
