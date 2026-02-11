import sys
import os
import time

# Add parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from py_broker_captrader.broker_data_source import BrokerDataSource
from py_manage_portfolio.data_source import OrderRequest

def reset_aapl():
    ds = BrokerDataSource(host="127.0.0.1", port=4002, client_id=0, auto_connect=True)
    if not ds.is_connected():
        print("Failed to connect")
        return

    try:
        # Check current position
        ib = ds._connection.ib
        positions = ib.positions()
        aapl_pos = next((p for p in positions if p.contract.symbol == "AAPL"), None)
        
        if aapl_pos:
            qty = aapl_pos.position
            print(f"Current AAPL position: {qty}")
            if qty > 1:
                sell_qty = qty - 1
                print(f"Selling {sell_qty} to reset to 1...")
                req = OrderRequest(symbol="AAPL", action="SELL", quantity=sell_qty, order_type="MKT")
                ds.place_order(req)
                time.sleep(2)
            elif qty < 1:
                buy_qty = 1 - qty
                print(f"Buying {buy_qty} to reset to 1...")
                req = OrderRequest(symbol="AAPL", action="BUY", quantity=buy_qty, order_type="MKT")
                ds.place_order(req)
                time.sleep(2)
            else:
                print("Position already at 1.")
        else:
            print("No AAPL position. Buying 1...")
            req = OrderRequest(symbol="AAPL", action="BUY", quantity=1, order_type="MKT")
            ds.place_order(req)
            time.sleep(2)
            
    finally:
        ds.disconnect()

if __name__ == "__main__":
    reset_aapl()
