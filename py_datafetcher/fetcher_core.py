import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
from .types import AppConfig, IDataProvider, AssetData, FxData, DataFetcherError, OHLCV
from .cache_manager import CacheManager
from .error_logger import ErrorLogger

class FetcherOrchestrator:
    def __init__(self, config: AppConfig, cache: CacheManager, providers: List[IDataProvider], error_logger: Optional[ErrorLogger] = None):
        self.config = config
        self.cache = cache
        self.providers = providers # These should be sorted by priority already
        self.error_logger = error_logger
        self.default_start_date = date(2020, 1, 1)

    def _get_start_date(self, last_update_str: str, hint_date: Optional[date] = None) -> date:
        """ 
        Determines the start date for fetching.
        If last_update_str is present, implies data exists up to that date. Start next day.
        Else use hint_date or default.
        """
        if last_update_str:
            try:
                # Assuming last_update is YYYY-MM-DD representing the last candle date
                # If it's a full ISO timestamp, we take the date part.
                # Let's try parsing flexible
                dt_obj = datetime.fromisoformat(last_update_str).date()
                return dt_obj + timedelta(days=1)
            except ValueError:
                logging.warning(f"Could not parse last_update '{last_update_str}'. Using default.")
        
        return hint_date if hint_date else self.default_start_date

    def update_asset(self, isin: str, ticker: str, start_date_hint: Optional[date] = None) -> bool:
        logging.info(f"Processing Asset {isin} (Ticker: {ticker})...")
        
        # 1. Load from Cache
        asset = self.cache.load_asset(isin)
        
        if asset:
            start_date = self._get_start_date(asset.last_update)
        else:
            start_date = start_date_hint if start_date_hint else self.default_start_date
            asset = None

        if start_date > date.today():
            logging.info(f"Asset {isin} up to date (Next fetch: {start_date}).")
            return True

        # 2. Use Ticker provided by arguments
        if not ticker:
             logging.error(f"No ticker provided for {isin}. Skipping.")
             if self.error_logger:
                 self.error_logger.log_failure(isin, "UNKNOWN", "No ticker provided")
             return False

        # 3. Provider Loop
        new_history: List[OHLCV] = []
        new_price: float = 0.0
        success = False
        fetched_symbol = ticker
        fetched_currency = "EUR" # Default, or we assume from provider

        # We need at least one provider to work
        for provider in self.providers:
            try:
                logging.info(f"Fetching {ticker} from {provider.__class__.__name__} starting {start_date}")
                
                # Fetch History
                # Optimization: Should we fetch only if start_date < today? Yes.
                hist_data = provider.fetch_asset_history(ticker, start_date)
                
                # Fetch Current Price
                # If hist_data includes today, we could use that close. 
                # But fetch_current_price might give real-time.
                try:
                    curr_price = provider.fetch_current_price(ticker)
                except:
                    # Fallback to last close in history
                    if hist_data:
                        curr_price = hist_data[-1].close
                    else:
                        curr_price = 0.0

                new_history = hist_data
                new_price = curr_price
                success = True
                break # Success
            except DataFetcherError as e:
                logging.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                continue
            except Exception as e:
                logging.exception(f"Unexpected error in provider {provider.__class__.__name__}: {e}")
                continue

        if not success:
            logging.error(f"All providers failed to update {isin}.")
            if self.error_logger:
                self.error_logger.log_failure(isin, ticker, "All providers failed")
            return False

        # 4. Merge and Save
        if asset is None:
            # Initialize new
            # Determine max date from new_history for last_update
            max_date = start_date # Minimum
            hist_dict = {}
            for h in new_history:
                hist_dict[h.date] = h
                if h.date > str(max_date):
                    max_date = h.date # String compare works for ISO dates
            
            asset = AssetData(
                isin=isin,
                symbol=fetched_symbol,
                currency=fetched_currency, # TODO: Parse from provider?
                market_price=new_price,
                last_update=str(max_date) if new_history else datetime.now().strftime("%Y-%m-%d"),
                history=hist_dict
            )
        else:
            # Update existing
            asset.market_price = new_price
            
            # Merge history
            for h in new_history:
                asset.history[h.date] = h
                if h.date > asset.last_update:
                    asset.last_update = h.date
        
        self.cache.save_asset(asset)
        logging.info(f"Successfully updated {isin}. New last_update: {asset.last_update}")
        return True

    def update_fx(self, pair: str, start_date_hint: Optional[date] = None) -> bool:
        logging.info(f"Processing FX {pair}...")
        fx_data = self.cache.load_fx(pair)
        
        if fx_data:
            start_date = self._get_start_date(fx_data.last_update)
        else:
            start_date = start_date_hint if start_date_hint else self.default_start_date

        if start_date > date.today():
             return True

        success = False
        new_rates: Dict[str, float] = {}
        
        for provider in self.providers:
            try:
                data = provider.fetch_fx_history(pair, start_date)
                if data:
                    new_rates = data
                    success = True
                    break
            except Exception as e:
                logging.warning(f"Provider failed for FX {pair}: {e}")
        
        if not success:
            logging.error(f"Failed to fetch FX {pair}")
            return False

        # Merge
        if fx_data is None:
            max_date = start_date
            if new_rates:
                max_date = max(new_rates.keys())
            
            # Current rate is last in history suitable?
            curr_rate = new_rates[max_date] if new_rates else 1.0
            
            fx_data = FxData(
                pair=pair,
                rate=curr_rate,
                last_update=str(max_date),
                history=new_rates
            )
        else:
            # Update
            if new_rates:
                fx_data.history.update(new_rates)
                latest_date = max(new_rates.keys())
                if latest_date > fx_data.last_update:
                    fx_data.last_update = latest_date
                    fx_data.rate = new_rates[latest_date]

        self.cache.save_fx(fx_data)
        return True
