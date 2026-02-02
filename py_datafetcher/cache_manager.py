import json
import os
import shutil
import logging
from typing import Optional, Dict
from dataclasses import asdict
from .types import AssetData, FxData, OHLCV

class CacheManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def _get_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def load_asset(self, isin: str) -> Optional[AssetData]:
        path = self._get_path(f"{isin}.json")
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Basic schema validation
            if "isin" not in data or "history" not in data:
                raise ValueError("Missing required keys in JSON")

            # Deserialize History
            history: Dict[str, OHLCV] = {}
            for date_str, candle in data.get("history", {}).items():
                history[date_str] = OHLCV(
                    date=date_str,
                    open=candle.get("open", 0.0),
                    high=candle.get("high", 0.0),
                    low=candle.get("low", 0.0),
                    close=candle.get("close", 0.0),
                    volume=candle.get("volume", 0)
                )

            return AssetData(
                isin=data["isin"],
                symbol=data.get("symbol", isin),
                currency=data.get("currency", "EUR"),
                market_price=data.get("market_price", 0.0),
                last_update=data.get("last_update", ""),
                history=history
            )

        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Cache corruption detected for {isin}: {e}")
            self._backup_corrupt_file(path)
            return None
        except Exception as e:
            logging.error(f"Error loading asset {isin}: {e}")
            return None

    def save_asset(self, asset: AssetData) -> None:
        path = self._get_path(f"{asset.isin}.json")
        tmp_path = path + ".tmp"
        
        try:
            # Serialize
            data = {
                "isin": asset.isin,
                "symbol": asset.symbol,
                "currency": asset.currency,
                "market_price": asset.market_price,
                "last_update": asset.last_update,
                "history": {
                    d: asdict(candle) for d, candle in asset.history.items()
                }
            }
            
            # Atomic Write
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            os.replace(tmp_path, path)
            
        except Exception as e:
            logging.error(f"Failed to save asset {asset.isin}: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def load_fx(self, pair: str) -> Optional[FxData]:
        path = self._get_path(f"{pair}.json")
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return FxData(
                pair=data.get("pair", pair),
                rate=data.get("rate", 1.0),
                last_update=data.get("last_update", ""),
                history=data.get("history", {})
            )
        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Cache corruption detected for FX {pair}: {e}")
            self._backup_corrupt_file(path)
            return None

    def save_fx(self, fx: FxData) -> None:
        path = self._get_path(f"{fx.pair}.json")
        tmp_path = path + ".tmp"
        
        try:
            data = {
                "pair": fx.pair,
                "rate": fx.rate,
                "last_update": fx.last_update,
                "history": fx.history
            }
            
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            os.replace(tmp_path, path)
        except Exception as e:
            logging.error(f"Failed to save FX {fx.pair}: {e}")

    def _backup_corrupt_file(self, path: str):
        try:
            backup_path = path + ".corrupt"
            shutil.move(path, backup_path)
            logging.info(f"Moved corrupt file to {backup_path}")
        except OSError as e:
            logging.error(f"Failed to backup corrupt file {path}: {e}")
