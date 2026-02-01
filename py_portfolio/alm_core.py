
import logging
import sys
from .xml_parser import TradeLogParser
from .trade_logic import TradeProcessor
from .market_data import FileMarketDataProvider
from .alm_xml_gen import XmlGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    # 0. Args
    input_file = "trades.xml"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    # 1. Setup
    parser = TradeLogParser()
    market_data = FileMarketDataProvider()
    processor = TradeProcessor(market_data)
    xml_gen = XmlGenerator()
    
    # 2. Parse
    logging.info(f"Parsing XML file {input_file}...")
    try:
        raw_events = parser.parse_file(input_file)
    except Exception as e:
        logging.error(f"Failed to parse input file: {e}")
        return
        
    logging.info(f"Parsed {len(raw_events)} events.")
    
    # 3. Process
    logging.info("Processing trades and calculating metrics...")
    results = []
    for event in raw_events:
        processed = processor.process_event(event)
        results.append(processed)
        
    # 4. Write XML
    output_file = "trades-history.xml"
    logging.info(f"Writing results to {output_file}...")
    try:
        xml_gen.generate(results, output_file)
        logging.info("Success.")
    except Exception as e:
        logging.error(f"Error generating XML: {e}")

if __name__ == "__main__":
    main()
