import yfinance as yf
from datetime import date, timedelta
from typing import List, Dict
import logging
from .types import IDataProvider, OHLCV, DataFetcherError

class YahooProvider(IDataProvider):
    def fetch_asset_history(self, ticker: str, start_date: date) -> List[OHLCV]:
        try:
            # yfinance expects string dates YYYY-MM-DD
            start_str = start_date.strftime("%Y-%m-%d")
            
            # Fetch data
            ticker_obj = yf.Ticker(ticker)
            # auto_adjust=True handles splits/dividends in Close, usually preferred for charts
            # But for trade matching, unadjusted might be better? 
            # Review IMP doesn't specify. Standard defaults usually ok.
            hist = ticker_obj.history(start=start_str, auto_adjust=True)
            
            if hist.empty:
                raise DataFetcherError(f"No data found for ticker {ticker} from {start_str}")

            results = []
            for dt, row in hist.iterrows():
                # dt is Timestamp, convert to string YYYY-MM-DD
                date_str = dt.strftime("%Y-%m-%d")
                
                # yfinance returns pandas Series for row
                results.append(OHLCV(
                    date=date_str,
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume'])
                ))
            
            return results

        except Exception as e:
            # Wrap standard exceptions int DataFetcherError for the Orchestrator
            raise DataFetcherError(f"Yahoo API Error for {ticker}: {e}")

    def fetch_current_price(self, ticker: str) -> float:
        try:
            ticker_obj = yf.Ticker(ticker)
            # Try fast info first (often available without full history)
            price = None
            
            # Different keys depending on yfinance version/asset type
            keys_to_try = ['currentPrice', 'regularMarketPrice', 'bid', 'ask']
            info = ticker_obj.info
            
            for k in keys_to_try:
                if k in info and info[k] is not None:
                    price = info[k]
                    break
            
            if price is None:
                # Fallback: get last close from 1d history
                hist = ticker_obj.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
            
            if price is None:
                raise DataFetcherError(f"Could not determine current price for {ticker}")
                
            return float(price)

        except Exception as e:
            raise DataFetcherError(f"Yahoo Price Error for {ticker}: {e}")

    def fetch_fx_history(self, pair: str, start_date: date) -> Dict[str, float]:
        # Pair format e.g. "USDEUR" -> Ticker "USDEUR=X" or "EUR=X"? 
        # yfinance convention: "EURUSD=X" gives USD per Euro? No, it's "BASEQUOTE=X" usually
        # But commonly "EURUSD=X" is 1.08 USD (~1 EUR).
        # We need to ensure we query the right symbol. 
        # If request is USDEUR (How many EUR for 1 USD?) -> "USDEUR=X" or "EUR=X" (inverse of EURUSD)
        # Yahoo supports "EURUSD=X" (USD per 1 EUR) and often "USDEUR=X"
        
        yf_symbol = f"{pair}=X"
        
        try:
            start_str = start_date.strftime("%Y-%m-%d")
            ticker_obj = yf.Ticker(yf_symbol)
            hist = ticker_obj.history(start=start_str)
            
            if hist.empty:
                 raise DataFetcherError(f"No FX data for {yf_symbol}")
            
            results = {}
            for dt, row in hist.iterrows():
                results[dt.strftime("%Y-%m-%d")] = float(row['Close'])
                
            return results
            
        except Exception as e:
            raise DataFetcherError(f"Yahoo FX Error for {pair}: {e}")
