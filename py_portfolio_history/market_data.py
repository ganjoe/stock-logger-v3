import os
import json
import logging
import subprocess
import sys
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, Any, Optional
from .domain import IMarketDataProvider

class MarketDataManager(IMarketDataProvider):
    def __init__(self, data_dir: str = "./data/market", log_file: str = "log_market_data.txt"):
        self.data_dir = data_dir
        self.cache_memory: Dict[str, Any] = {} # In-memory cache optimization
        self.failed_fetches: set = set() # Track failed fetches to avoid retries
        self.failed_tickers: set = set() # Track tickers that failed (never retry)
        self.log_file = log_file
        self.logged_warnings: set = set() # Track warnings already logged to reduce spam

    def _get_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def _load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        if filename in self.cache_memory:
            return self.cache_memory[filename]
        
        path = self._get_path(filename)
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.cache_memory[filename] = data
                return data
        except Exception as e:
            logging.error(f"Failed to load JSON {path}: {e}")
            return None

    def _trigger_lazy_fetch(self, asset_arg: str, is_fx: bool = False) -> bool:
        """ Triggers datafetcher.py via subprocess """
        logging.info(f"Triggering Lazy Fetch for {'FX ' if is_fx else ''}{asset_arg}")
        
        # Use module execution to handle package imports correctly
        logging.info(f"Subprocess Executable: {sys.executable}")
        cmd = [sys.executable, "-m", "py_datafetcher.datafetcher", "--mode", "update"]
        if is_fx:
            cmd.extend(["--fx", asset_arg])
        else:
            cmd.extend(["--assets", asset_arg])
            
        try:
            # We assume datafetcher.py is in current working directory or path needs adjustment
            # Assuming CWD is project root
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"Lazy fetch successful.")
                return True
            else:
                logging.error(f"Lazy fetch failed: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Subprocess call failed: {e}")
            return False

    def get_market_price(self, isin: str, ticker: str, query_date: date) -> Decimal:
        filename = f"{isin}.json"
        
        # 1. Try Load
        data = self._load_json(filename)
        
        query_str = query_date.strftime("%Y-%m-%d")
        
        # 2. Check if data present
        price_found = None
        last_update_str = None
        if data:
            if "history" in data:
                if query_str in data["history"]:
                    price_found = data["history"][query_str].get("close")
            last_update_str = data.get("last_update")
        
        # 3. On Miss -> Fetch
        should_fetch = False
        if price_found is None:
            # Check if we already covered this date
            if last_update_str:
                try:
                    last_upd = datetime.strptime(last_update_str, "%Y-%m-%d").date()
                    if query_date <= last_upd:
                        # Date is in the past coverage, so it must be a missing day (weekend/holiday)
                        # Do not fetch.
                        should_fetch = False
                    else:
                        # Date is newer than our cache
                        should_fetch = True
                except:
                    should_fetch = True
            else:
                # No cache or no last_update
                should_fetch = True
                
        if should_fetch:
            # Check if this ticker has already failed before
            if ticker in self.failed_tickers:
                logging.debug(f"Skipping ticker that previously failed: {ticker}")
            else:
                # Construct arg ISIN:TICKER:DATE
                arg = f"{isin}:{ticker}:{query_str}"
                
                # Check if this exact fetch was already attempted and failed
                if arg in self.failed_fetches:
                    logging.debug(f"Skipping already-failed fetch: {arg}")
                else:
                    # Flush memory cache for this file if we are going to update it
                    if filename in self.cache_memory:
                        del self.cache_memory[filename]
                        
                    if self._trigger_lazy_fetch(arg, is_fx=False):
                        # Reload
                        data = self._load_json(filename)
                        if data and "history" in data:
                             if query_str in data["history"]:
                                price_found = data["history"][query_str].get("close")
                    else:
                        # Mark ticker as permanently failed
                        self.failed_tickers.add(ticker)
                        self.failed_fetches.add(arg)
                        self._log_failed_fetch(f"PRICE: {arg} (ticker {ticker} blocked)")
        
        # 4. Return or Fallback
        if price_found is not None:
             return Decimal(str(price_found))
        
        # Only log warning once per unique ISIN/date combo
        warn_key = f"PRICE:{isin}:{query_str}"
        if warn_key not in self.logged_warnings:
            logging.warning(f"Price not found for {isin} on {query_str}. Using Fallback 0.00")
            self.logged_warnings.add(warn_key)
        return Decimal("0.00")

    def get_fx_rate(self, from_curr: str, to_curr: str, query_date: date) -> Decimal:
        if from_curr == to_curr:
            return Decimal("1.0")
            
        # Standardize pair name? e.g. USDEUR vs EURUSD
        # The fetcher seems to support saving by pair name requested.
        # Let's assume we want FROM -> TO.
        pair = f"{from_curr}{to_curr}"
        filename = f"{pair}.json"
        
        data = self._load_json(filename)
        query_str = query_date.strftime("%Y-%m-%d")
        
        rate_found = None
        last_update_str = None
        if data:
            if "history" in data:
                 if query_str in data["history"]:
                     rate_found = data["history"][query_str]
            last_update_str = data.get("last_update")
        
        should_fetch = False
        if rate_found is None:
             if last_update_str:
                try:
                    last_upd = datetime.strptime(last_update_str, "%Y-%m-%d").date()
                    if query_date <= last_upd:
                        should_fetch = False
                    else:
                        should_fetch = True
                except:
                    should_fetch = True
             else:
                should_fetch = True
        
        if should_fetch:
            arg = f"{pair}:{query_str}"
            
            # Check if this fetch was already attempted and failed
            if arg in self.failed_fetches:
                logging.debug(f"Skipping already-failed FX fetch: {arg}")
            else:
                if filename in self.cache_memory:
                    del self.cache_memory[filename]
                    
                if self._trigger_lazy_fetch(arg, is_fx=True):
                    data = self._load_json(filename)
                    if data and "history" in data:
                         if query_str in data["history"]:
                             rate_found = data["history"][query_str]
                else:
                    # Mark as failed to prevent retry
                    self.failed_fetches.add(arg)
                    self._log_failed_fetch(f"FX: {arg}")
                         
        if rate_found is not None:
            return Decimal(str(rate_found))
        
        # Only log warning once per unique pair/date combo
        warn_key = f"FX:{pair}:{query_str}"
        if warn_key not in self.logged_warnings:
            logging.warning(f"FX Rate not found for {pair} on {query_str}. Using Fallback 1.0")
            self.logged_warnings.add(warn_key)
        return Decimal("1.0")
    
    def _log_failed_fetch(self, entry: str):
        """ Write failed fetch to persistent log file """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp} - {entry}\n")
        except Exception as e:
            logging.error(f"Failed to write to {self.log_file}: {e}")
