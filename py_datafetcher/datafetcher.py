import argparse
import sys
import logging
from datetime import date
from py_datafetcher.service import DataFetcherService
from py_datafetcher.data_models import ProviderType

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
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging (DEBUG)")
    
    args = parser.parse_args()
    
    # We keep the --verbose flag for future use, but don't flood with DEBUG logs 
    # to avoid yfinance's internal noise.
    
    logging.info("Starting DataFetcher via Service API...")
    
    # Initialize Service
    service = DataFetcherService()
    
    success_count = 0
    fail_count = 0
    
    # 2. Process Assets
    if args.assets:
        assets_to_fetch = parse_asset_list(args.assets)
        for isin, ticker, _ in assets_to_fetch:
            # CLI mode implies we want to ensure data is up to date.
            # We use force_update=True to trigger the update logic (which internally checks if update is actually needed vs today)
            # Actually, the logic in service.get_asset with force_update=True will trigger orchestrator.update_asset.
            # orchestrator.update_asset checks "if start_date > date.today(): return True".
            # So force_update=True here is safe and correct for "Update Mode".
            asset = service.get_asset(isin, ticker, force_update=True)
            if asset:
                 success_count += 1
            else:
                 fail_count += 1
                 
    # 3. Process FX
    if args.fx:
        fx_to_fetch = parse_fx_list(args.fx)
        for pair, _ in fx_to_fetch:
            fx_data = service.get_fx(pair, force_update=True)
            if fx_data:
                success_count += 1
            else:
                fail_count += 1
    
    logging.info(f"DataFetcher Finished. Success: {success_count}, Failed: {fail_count}")
    
    if fail_count > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
