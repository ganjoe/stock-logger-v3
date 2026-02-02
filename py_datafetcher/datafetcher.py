import argparse
import sys
import logging
from datetime import date
from py_datafetcher.types import ProviderType
from py_datafetcher.config_loader import load_config
from py_datafetcher.cache_manager import CacheManager
from py_datafetcher.provider_yahoo import YahooProvider
from py_datafetcher.fetcher_core import FetcherOrchestrator

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def parse_asset_list(arg_str: str) -> list:
    """ Parses 'ISIN:TICKER:DATE,ISIN2:TICKER2:DATE' into [(isin, ticker, date_obj), ...] """
    if not arg_str:
        return []
    
    items = []
    parts = arg_str.split(',')
    for p in parts:
        p = p.strip()
        if not p: continue
        
        # Format expects ISIN:TICKER:DATE
        # Be robust: Split by ':'
        subparts = p.split(':')
        
        if len(subparts) >= 3:
            isin = subparts[0]
            ticker = subparts[1]
            date_str = subparts[2]
            try:
                dt = date.fromisoformat(date_str)
                items.append((isin, ticker, dt))
            except ValueError:
                logging.warning(f"Invalid date format in {p}. Using default.")
                items.append((isin, ticker, None))
        elif len(subparts) == 2:
            # Fallback format ISIN:TICKER? Or ISIN:DATE?
            # User requirement says ISIN:TICKER:DATE.
            # But let's assume if 2 parts -> ISIN:TICKER (Date=None)
             items.append((subparts[0], subparts[1], None))
        else:
             logging.warning(f"Invalid asset format '{p}'. Expected ISIN:TICKER:DATE")
        
    return items

def parse_fx_list(arg_str: str) -> list:
    """ Parses 'PAIR:DATE,...' -> [(pair, date_obj)] """
    if not arg_str:
        return []
    items = []
    parts = arg_str.split(',')
    for p in parts:
        p = p.strip()
        if not p: continue
        
        start_date = None
        if ':' in p:
             key, date_str = p.split(':', 1)
             try:
                 start_date = date.fromisoformat(date_str)
                 items.append((key, start_date))
             except ValueError:
                 items.append((key, None))
        else:
             items.append((p, None))
    return items

def main():
    parser = argparse.ArgumentParser(description="Stock Logger Data Fetcher")
    parser.add_argument("--mode", required=True, choices=["update"], help="Operation mode")
    parser.add_argument("--assets", help="List of assets 'ISIN:TICKER:STARTDATE,...'")
    parser.add_argument("--fx", help="List of FX pairs 'PAIR:STARTDATE,...'")
    
    args = parser.parse_args()
    
    logging.info("Starting DataFetcher...")
    
    # 1. Load Config & Init Components
    config = load_config()
    cache = CacheManager(config.market_data_dir)
    
    providers = []
    # Instantiate Providers based on Config
    for p_conf in config.providers:
        if p_conf.name == ProviderType.YAHOO:
            providers.append(YahooProvider())
        # Add other providers here if implemented
        
    orchestrator = FetcherOrchestrator(config, cache, providers)
    
    success_count = 0
    fail_count = 0
    
    # 2. Process Assets
    if args.assets:
        assets_to_fetch = parse_asset_list(args.assets)
        for isin, ticker, start_date in assets_to_fetch:
            if orchestrator.update_asset(isin, ticker, start_date):
                success_count += 1
            else:
                fail_count += 1
                
    # 3. Process FX
    if args.fx:
        fx_to_fetch = parse_fx_list(args.fx)
        for pair, start_date in fx_to_fetch:
            if orchestrator.update_fx(pair, start_date):
                success_count += 1
            else:
                fail_count += 1
    
    logging.info(f"DataFetcher Finished. Success: {success_count}, Failed: {fail_count}")
    
    # Return 0 if all good, 1 if some failures? 
    # Or strict: non-zero if ANY failure.
    if fail_count > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
