import sys
import argparse
import logging
from datetime import datetime

from .market_data import MarketDataManager
from .xml_parser import XmlInputParser
from .calculator import PortfolioCalculator, IMarketDataProvider
# from .xml_generator import XmlOutputGenerator # Legacy
from .csv_generator import CsvOutputGenerator
from .types import EventWithSnapshot

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    parser = argparse.ArgumentParser(description="Portfolio History Analyzer")
    parser.add_argument("--input", default="trades.xml", help="Input XML file (default: trades.xml)")
    parser.add_argument("--output", default="journal.csv", help="Output CSV file (default: journal.csv)")
    args = parser.parse_args()

    logging.info("Starting Portfolio History Analysis...")
    
    # 1. Components
    # MarketDataManager implements IMarketDataProvider
    market_data = MarketDataManager("./data/market")
    xml_parser = XmlInputParser()
    calculator = PortfolioCalculator(market_data)
    # xml_gen = XmlOutputGenerator() 
    csv_gen = CsvOutputGenerator()

    # 2. Parse Input (Unified)
    logging.info(f"Parsing input: {args.input}")
    transactions = xml_parser.parse_all(args.input)
    
    if not transactions:
        logging.warning("No transactions found.")
        return

    # 3. Sort Transactions
    # Sort by date, then maybe ID or stable sort?
    # Usually ID is chronological string, but date is primary.
    # transactions (types.py) has 'date' as datetime.
    transactions.sort(key=lambda x: x.date)
    
    history_events = []
    
    # 4. Process Loop
    logging.info("Processing transactions...")
    for t in transactions:
        snapshot = calculator.process_transaction(t)
        history_events.append(EventWithSnapshot(t, snapshot))
        
    # 5. Generate Output (CSV)
    logging.info(f"Generating CSV: {args.output}")
    csv_str = csv_gen.generate(history_events)
    
    with open(args.output, "w", encoding='utf-8') as f:
        f.write(csv_str)
        
    logging.info(f"Done. Output written to {args.output}")
    
    # Final Summary Log
    metrics = calculator.snapshots[-1].performance if calculator.snapshots else None
    if metrics:
        logging.info(f"Total Transactions: {metrics.total_transactions_count}")
        logging.info(f"Total Realized PnL: {metrics.realized_pnl:.2f} EUR")
    
    logging.info(f"Done.")

if __name__ == "__main__":
    main()
