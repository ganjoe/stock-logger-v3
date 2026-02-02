import json
import os
import logging
from typing import Dict, List
from .types import AppConfig, ProviderConfig, ProviderType

def load_config(config_path: str = "providers.json", isin_map_path: str = "isin_map.json") -> AppConfig:
    """ 
    Loads provider settings and ISIN map. 
    Validates basic structure and ensures market data directory exists.
    """
    
    # Defaults
    providers = []
    ticker_map = {}
    market_data_dir = "./data/market"
    
    # 1. Load Providers
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                
                # Check for new dict-based structure
                if "providers" in data and isinstance(data["providers"], dict):
                    # Iterate over dict items
                    for p_key, p_data in data["providers"].items():
                        if not p_data.get("enabled", True):
                            continue
                            
                        try:
                            # Use key as fallback for name if strictly needed, 
                            # but Enum matching usually expects specific strings like "YAHOO"
                            # p_key might be "yahoo" or "alpha_vantage"
                            p_type_str = p_key.upper()
                            # Map partial names if needed, or rely on strict Enum match
                            if p_type_str == "ALPHA_VANTAGE": p_type_str = "ALPHAVANTAGE"
                            
                            p_type = ProviderType(p_type_str)
                            
                            providers.append(ProviderConfig(
                                name=p_type,
                                api_key=p_data.get("api_key"),
                                priority=p_data.get("priority", 99),
                                rate_limit_ms=1000 # TODO: Parse textual rate limits if needed
                            ))
                        except (ValueError, KeyError) as e:
                            logging.warning(f"Skipping provider {p_key}: {e}")
                
                # Support Legacy List format just in case? No, strict switch.
                
                # Load optional data dir override (if present in global_settings or root)
                if "market_data_dir" in data:
                    market_data_dir = data["market_data_dir"]
                    
        except Exception as e:
            logging.error(f"Failed to load config file {config_path}: {e}")
    else:
        logging.info(f"Config file {config_path} not found. Using default defaults.")

    # 2. Add Default Provider if list empty
    if not providers:
        logging.info("No active providers configured. Adding Default YAHOO provider.")
        providers.append(ProviderConfig(name=ProviderType.YAHOO, priority=1))

    # Sort
    providers.sort(key=lambda x: x.priority)

    # 3. Load ISIN Map (formerly ticker_map logic in this context)
    if os.path.exists(isin_map_path):
        try:
            with open(isin_map_path, 'r') as f:
                loaded_map = json.load(f)
                if isinstance(loaded_map, dict):
                    ticker_map = loaded_map
        except Exception as e:
            logging.warning(f"Failed to load ISIN map {isin_map_path}: {e}")

    # 4. Create Data Directory
    os.makedirs(market_data_dir, exist_ok=True)

    return AppConfig(
        providers=providers,
        ticker_map=ticker_map,
        market_data_dir=market_data_dir
    )
