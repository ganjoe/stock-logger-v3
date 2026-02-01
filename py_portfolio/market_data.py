
import json
import os
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .alm_types import MarketDataProvider

class FileMarketDataProvider(MarketDataProvider):
    def __init__(self, data_dir: str = "./data/market"):
        self.data_dir = data_dir
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_fx_rate(self, currency_pair: str, date_str: str) -> Decimal:
        """
        Reads {pair}.json, looks up date. Returns 1.0 if pair is EUREUR or file not found.
        date_str format: YYYY-MM-DD.
        """
        # Base case: Euro to Euro is always 1.0
        if currency_pair == "EUREUR":
            return Decimal("1.0")

        # Load file into cache if not present
        if currency_pair not in self._cache:
            file_path = os.path.join(self.data_dir, f"{currency_pair}.json")
            if not os.path.exists(file_path):
                # Fallback as per requirement: return 1.0 if file missing (silent fallback)
                return Decimal("1.0")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache[currency_pair] = data.get("history", {})
            except (json.JSONDecodeError, IOError):
                return Decimal("1.0")

        history = self._cache[currency_pair]
        
        # Exact match
        if date_str in history:
            return Decimal(str(history[date_str]))
            
        # If not found, try to find the closest previous date (simple fallback behavior)
        # This prevents 0.0 or 1.0 jumps on non-trading days/weekends if data is missing
        # However, for strict compliance with "lookup via date", we might just return 1.0 or last available.
        # Given the "silent fallback" nature, 1.0 is safest if exact date missing, or last known?
        # Let's stick to requirements: "Lookup via Datum". If missing -> 1.0.
        
        return Decimal("1.0")
