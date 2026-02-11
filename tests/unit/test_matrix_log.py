
from py_datafetcher import DataFetcherService
import os

service = DataFetcherService()

# Try a known invalid ticker
print("Attempting to fetch invalid asset...")
service.get_asset("INVALID_ISIN", ticker="INVALID_TICKER", force_update=True)

# Check if the log file exists and show content
log_path = os.path.join(service.config.market_data_dir, "log_ticker_failed.csv")
if os.path.exists(log_path):
    print(f"\nContent of {log_path}:")
    with open(log_path, 'r') as f:
        print(f.read())
else:
    print(f"\nError: {log_path} was not created.")
