import sys
import os
import time
from datetime import datetime

# Add parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from py_broker_captrader.broker_data_source import BrokerDataSource
from py_manage_portfolio.service import PortfolioService
from py_manage_portfolio.data_source import OrderRequest, OrderStatus

def test_market_order_flow():
    # 1. Setup
    ds = BrokerDataSource(host="127.0.0.1", port=4002, client_id=0, auto_connect=True)
    if not ds.is_connected():
        print("FAIL: Could not connect to IBKR")
        return
    
    service = PortfolioService(project_root=parent_dir, context="live", data_source=ds)
    symbol = "AAPL"
    
    try:
        # 2. Get Initial State
        service.load_portfolio_state()
        initial_qty = 0
        if symbol in service.state.positions:
            initial_qty = service.state.positions[symbol].quantity
        print(f"\n--- [START] Initial Quantity: {initial_qty} ---")

        # 3. Place Market BUY
        print(f"Placing Market BUY for 1 {symbol}...")
        req = OrderRequest(symbol=symbol, action="BUY", quantity=1, order_type="MKT")
        order_id = ds.place_order(req)
        print(f"Order ID: {order_id}")
        
        # 4. Immediate Check: Open Orders vs Portfolio
        print("\n--- [CHECK 1] Immediate Verification ---")
        time.sleep(1) # Small sleep for IBKR processing
        
        open_orders = ds.get_open_orders()
        is_in_open = any(o.symbol == symbol and o.order_type == "MKT" for o in open_orders)
        print(f"Is Market Order in Open Orders? {is_in_open}")
        
        # Refresh service state
        service.get_open_positions(update_prices=True)
        new_qty = service.state.positions[symbol].quantity
        is_executed = (new_qty == initial_qty + 1)
        print(f"Is Order Executed (New Qty: {new_qty})? {is_executed}")
        
        if not is_in_open and is_executed:
            print("✅ VERIFIED: Market order is NOT in open orders and IS executed in portfolio.")
        else:
            print("❌ FAILED: Unexpected state for market order.")

        # 5. Place Market SELL
        print(f"\nPlacing Market SELL for 1 {symbol}...")
        req = OrderRequest(symbol=symbol, action="SELL", quantity=1, order_type="MKT")
        ds.place_order(req)
        
        # 6. Final Check
        print("\n--- [CHECK 2] Final Verification ---")
        time.sleep(1)
        
        open_orders = ds.get_open_orders()
        is_in_open = any(o.symbol == symbol and o.order_type == "MKT" for o in open_orders)
        print(f"Is Market Order in Open Orders? {is_in_open}")
        
        service.get_open_positions(update_prices=True)
        final_qty = service.state.positions[symbol].quantity
        is_executed = (final_qty == initial_qty)
        print(f"Is Sell Executed (Final Qty: {final_qty})? {is_executed}")
        
        if not is_in_open and is_executed:
            print("✅ VERIFIED: Sell order is NOT in open orders and IS executed in portfolio.")

    finally:
        ds.disconnect()

if __name__ == "__main__":
    test_market_order_flow()
