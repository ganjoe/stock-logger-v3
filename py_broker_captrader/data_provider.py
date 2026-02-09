"""
Broker Data Provider Implementation.

Implements AbstractDataProvider (conceptually) to fetch historical data from IBKR.
Designed to be used as a secondary source for DataFetcherService.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import time
from dataclasses import dataclass

from .connection import IBKRConnection

@dataclass
class BarData:
    """Standard OHLCV Bar"""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class BrokerDataProvider:
    """
    Fetches historical market data from IBKR via shared connection.
    
    Handles:
    - Contract qualification
    - Historical Data Requests
    - Rate Limiting (Pacing Violations)
    """
    
    def __init__(self, connection: IBKRConnection):
        self._connection = connection

    def get_daily_history(self, symbol: str, days: int = 365) -> List[BarData]:
        """
        Fetches daily bars from IBKR.
        
        Args:
            symbol: Ticker symbol (e.g. 'AAPL')
            days: Number of days validation history (default 365)
            
        Returns:
            List of BarData objects (sorted by date, oldest first)
        """
        if not self._connection.is_connected():
            if not self._connection.connect():
                 raise ConnectionError("Could not connect to IBKR")
            
        ib = self._connection.ib
        
        try:
            from ib_insync import Stock, util
        except ImportError:
            raise ImportError("ib_insync required")

        # Qualify Contract
        contract = Stock(symbol, 'SMART', 'USD')
        try:
            qual_contracts = ib.qualifyContracts(contract)
            if not qual_contracts:
                print(f"⚠ Symbol {symbol} not found/ambiguous.")
                return []
            contract = qual_contracts[0]
        except Exception as e:
            print(f"⚠ Contract qualification failed for {symbol}: {e}")
            return []

        # Request History
        # 'ADJUSTED_LAST' compensates for splits/dividends
        # 'TRADES' usually best for volume, 'MIDPOINT' if no market data sub
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=f'{days} D',
                barSizeSetting='1 day',
                whatToShow='ADJUSTED_LAST',
                useRTH=True,
                formatDate=1, # 1=yyyymmdd
                keepUpToDate=False
            )
            
            # Convert to internal BarData
            result = []
            for bar in bars:
                # ib_insync returns date as date or datetime depending on barSize
                dt = bar.date
                if not isinstance(dt, datetime):
                     dt = datetime(dt.year, dt.month, dt.day)
                
                result.append(BarData(
                    date=dt,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume if bar.volume else 0.0)
                ))
            
            return result
            
        except Exception as e:
            # Check for Pacing Violation (Code 162)
            if "162" in str(e):
                print(f"⚠ Pacing Violation for {symbol}: {e}")
            else:
                print(f"⚠ History fetch failed for {symbol}: {e}")
            return []

    def get_batch_history(self, symbols: List[str], days: int = 365) -> Dict[str, List[BarData]]:
        """
        Fetches data for multiple symbols respecting pacing constraints.
        
        Note: IBKR limits concurrent historical requests (typ. 50).
        High-frequency requests trigger Pacing Violation (162).
        """
        results = {}
        for symbol in symbols:
            try:
                # Sequential fetch is safest for "Junior" implementation to adhere to ICD-BRK-010
                # Could be parallelized with Semaphore later
                # Wait slightly to be nice to API
                time.sleep(0.5) 
                
                data = self.get_daily_history(symbol, days)
                if data:
                    results[symbol] = data
            except Exception as e:
                print(f"Error fetching batch {symbol}: {e}")
                
        return results
