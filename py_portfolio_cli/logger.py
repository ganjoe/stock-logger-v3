import os
import csv
from datetime import datetime
from py_manage_portfolio.service import PortfolioService
from py_manage_portfolio.data_source import OrderRequest

JOURNAL_HEADERS = [
    "date", "time", "Trade_PnL", "Trade_R", "Fee", "Cashflow", "Dividend",
    "Equity", "Cash", "Total_Assets", "Drawdown", "Sum_Deposit", "Sum_Withdrawal",
    "Sum_Dividend", "Sum_Fee", "Trade_Count", "Open_Positions", "event",
    "symbol", "quantity", "price", "ticker", "ordertyp"
]

def append_trade_log(service: PortfolioService, request: OrderRequest, order_id: str):
    """
    Appends a successful trade to the broker-specific journal CSV.
    File is chosen based on the port (4001 -> journal_ib.csv, 4002 -> journal_ib_paper.csv).
    """
    ds = service.get_data_source()
    if not ds or not hasattr(ds, 'port'):
        return

    # Determine filename based on port
    port = ds.port
    filename = "journal_ib.csv" if port == 4001 else "journal_ib_paper.csv" if port == 4002 else f"journal_port_{port}.csv"
    path = os.path.join(service.project_root, "data", filename)

    # Ensure data directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Initialize file with headers if it doesn't exist
    file_exists = os.path.exists(path)
    
    # Get current metrics
    equity, cash, exposure = service._get_journal_metrics()
    
    # Current time
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Data row
    # event is 'buy' or 'sell' (lowercase to match legacy journal)
    event = request.action.lower()
    
    # Determine price from request (LMT > STP > 0 for log)
    price = request.limit_price or request.stop_price or 0.0

    row = {
        "date": date_str,
        "time": time_str,
        "Trade_PnL": "0.00", # New trade doesn't have PnL yet
        "Trade_R": "0",
        "Fee": "2.00", # Default fee assumption for logging
        "Cashflow": "0.00",
        "Dividend": "0.00",
        "Equity": f"{equity:.2f}",
        "Cash": f"{cash:.2f}",
        "Total_Assets": f"{exposure:.2f}",
        "Drawdown": "0.00", # Need history for this
        "Sum_Deposit": "0.00",
        "Sum_Withdrawal": "0.00",
        "Sum_Dividend": "0.00",
        "Sum_Fee": "0.00",
        "Trade_Count": "0",
        "Open_Positions": str(len(service.get_open_positions())),
        "event": event,
        "symbol": request.symbol,
        "quantity": f"{request.quantity:.2f}",
        "price": f"{price:.2f}",
        "ticker": request.symbol, # As per user request, ticker is symbol
        "ordertyp": request.order_type
    }

    try:
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=JOURNAL_HEADERS, delimiter=';')
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"  ✓ Trade logged to {filename}")
    except Exception as e:
        print(f"  ⚠️ Could not log trade to CSV: {e}")
