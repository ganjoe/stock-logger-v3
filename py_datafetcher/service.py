
import logging
from typing import Optional, List
from .data_models import AssetData, FxData, AppConfig, ProviderType
from .config_loader import load_config
from .cache_manager import CacheManager
from .error_logger import ErrorLogger
from .provider_yahoo import YahooProvider
from .fetcher_core import FetcherOrchestrator 

class DataFetcherService:
    def __init__(self, config_path: str = None):
        """
        Initializes the DataFetcher Service with configuration, cache manager, error logger, and providers.
        """
        self.config = load_config(config_path) if config_path else load_config()
        self.cache = CacheManager(self.config.market_data_dir)
        
        # Extract provider names for matrix logging
        provider_names = [p.name.value for p in self.config.providers]
        self.error_logger = ErrorLogger(self.config.market_data_dir, provider_names)
        
        # Initialize Providers based on Config
        self.providers = []
        for p_conf in self.config.providers:
            if p_conf.name == ProviderType.YAHOO:
                self.providers.append(YahooProvider())
            # Add other providers here if implemented
        
        # Initialize Orchestrator
        self.orchestrator = FetcherOrchestrator(self.config, self.cache, self.providers, self.error_logger)

    def get_asset(self, isin: str, ticker: Optional[str] = None, force_update: bool = False) -> Optional[AssetData]:
        """
        Retrieves asset data using a Cache-Through pattern.
        1. Checks Cache.
        2. If force_update implies fetch, or if cache is stale/missing, fetching is attempted.
        3. Returns the AssetData object (updated or cached).
        """
        asset = self.cache.load_asset(isin)
        
        # Determine if we need to update
        # Simple check: Is data missing? Or is force_update requested?
        # A more complex check could be: Is last_update < today? (But Orchestrator handles that efficiently too)
        
        needs_update = False
        
        if asset is None:
            needs_update = True
        elif force_update:
            needs_update = True
        
        if needs_update:
            # We need a ticker to fetch. 
            # If we don't have one passed in, do we have one in the cached asset (even if stale)?
            target_ticker = ticker
            if not target_ticker and asset:
                target_ticker = asset.symbol
            
            if target_ticker:
                # Orchestrator handles the fetching logic (providers, logging, merging)
                # It returns True/False for success.
                # If successful, it writes to cache.
                success = self.orchestrator.update_asset(isin, target_ticker)
                
                if success:
                    # Reload fresh data
                    asset = self.cache.load_asset(isin)
                else:
                    # Fetch failed. If we had old data (asset), we return that (stale is better than none).
                    # If we had no data, asset remains None.
                    pass
            else:
                logging.warning(f"Cannot update asset {isin}: No ticker provided and no cached symbol found.")
        
        return asset

    def get_fx(self, pair: str, force_update: bool = False) -> Optional[FxData]:
        """
        Retrieves FX data using a Cache-Through pattern.
        """
        fx_data = self.cache.load_fx(pair)
        
        needs_update = False
        if fx_data is None:
            needs_update = True
        elif force_update:
            needs_update = True
            
        if needs_update:
            success = self.orchestrator.update_fx(pair)
            
            if success:
                fx_data = self.cache.load_fx(pair)
            else:
                pass
                
        return fx_data
