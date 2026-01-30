
import csv
import logging
from xml_parser import TradeLogParser
from trade_logic import TradeProcessor
from market_data import FileMarketDataProvider
from alm_types import ProcessedEvent, TransactionType

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    # 1. Setup
    parser = TradeLogParser()
    market_data = FileMarketDataProvider()
    processor = TradeProcessor(market_data)
    
    # 2. Parse
    logging.info("Parsing XML file...")
    # Use real file 'trades.xml' by default, or could be arg.
    raw_events = parser.parse_file("trades.xml")
    logging.info(f"Parsed {len(raw_events)} events.")
    
    # 3. Process
    logging.info("Processing trades and calculating metrics...")
    results = []
    for event in raw_events:
        processed = processor.process_event(event)
        results.append(processed)
        
    # 4. Write CSV
    output_file = "alm_trades-history.csv"
    logging.info(f"Writing results to {output_file}...")
    write_csv(results, output_file)
    logging.info("Done.")

def write_csv(events: list[ProcessedEvent], filename: str):
    fieldnames = [
        'ID', 'Date', 'Type', 'Symbol', 
        'Quantity', 'EntryPrice', 'ExitPrice', 'FXRate',
        'PnL', 'Total Equity', 'Equity Curve', 'Cum Inflow',
        'Cum WinRate', 'Cum ProfitFactor', 'Drawdown'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for ev in events:
                row = {
                    'ID': ev.event_id,
                    'Date': ev.date.strftime("%Y-%m-%d %H:%M:%S"),
                    'Type': ev.type.value,
                    'Symbol': ev.symbol if ev.symbol else "",
                    'Quantity': f"{ev.quantity:.4f}",
                    'EntryPrice': f"{ev.entry_price:.4f}",
                    'ExitPrice': f"{ev.exit_price:.4f}",
                    'FXRate': f"{ev.fx_rate:.4f}",
                    'PnL': f"{ev.pnl:.2f}",
                    'Total Equity': f"{ev.total_equity:.2f}",
                    'Equity Curve': f"{ev.equity_curve:.2f}",
                    'Cum Inflow': f"{ev.cum_inflow:.2f}",
                    'Cum WinRate': f"{ev.cum_win_rate:.2f}%",
                    'Cum ProfitFactor': f"{ev.cum_profit_factor:.3f}",
                    'Drawdown': f"{ev.drawdown:.2f}%"
                }
                writer.writerow(row)
    except IOError as e:
        logging.error(f"Error writing CSV: {e}")

if __name__ == "__main__":
    main()
