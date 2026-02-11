import sys
import os
import time
import random
from datetime import datetime

# Add parent directory to sys.path to allow running this script directly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from py_broker_captrader.broker_data_source import BrokerDataSource
from py_manage_portfolio.data_source import OrderRequest

def verify_order_gone(ds, order_id, label="Order"):
    """Fetch open orders and ensure the given order_id is NOT present."""
    print(f"Checking if {label} {order_id} is gone...")
    for _ in range(5):
        time.sleep(1)
        open_orders = ds.get_open_orders()
        found = False
        for o in open_orders:
            if o.order_id == order_id:
                print(f"  ... still found with status: {o.status}")
                found = True
                break
        if not found:
            print(f"✅ {label} {order_id} correctly removed from open orders.")
            return True
    
    print(f"❌ {label} {order_id} still found in open orders after 5 seconds!")
    return False

def test_order_management():
    # Use Client ID 0 as standard
    client_id = 0
    print(f"Connecting with client_id: {client_id} to port 4002")
    
    ds = BrokerDataSource(host="127.0.0.1", port=4002, client_id=client_id, auto_connect=True)
    
    if not ds.is_connected():
        print("Failed to connect to IBKR")
        return

    try:
        print("\n--- PHASE 1: Fetch Existing Orders ---")
        open_orders = ds.get_open_orders()
        print(f"Initial open orders count: {len(open_orders)}")
        for o in open_orders:
            print(f"  Existing Order: {o.symbol} {o.action} {o.quantity} {o.order_type} status={o.status}")

        print("\n--- PHASE 2: Place & Cancel Limit Order ---")
        test_symbol = "AAPL"
        limit_request = OrderRequest(
            symbol=test_symbol,
            action="BUY",
            quantity=1,
            order_type="LMT",
            limit_price=10.0,
            time_in_force="DAY"
        )
        
        lmt_order_id = ds.place_order(limit_request)
        if lmt_order_id:
            print(f"Placed LIMIT order. ID: {lmt_order_id}")
            time.sleep(2)
            
            if any(o.order_id == lmt_order_id for o in ds.get_open_orders()):
                print(f"✅ LIMIT order {lmt_order_id} visible in open orders.")
                
                print(f"Cancelling LIMIT order {lmt_order_id}...")
                ds.cancel_order(lmt_order_id)
                verify_order_gone(ds, lmt_order_id, "LIMIT order")
            else:
                print(f"❌ LIMIT order {lmt_order_id} NOT found after placement!")
        else:
            print("❌ Failed to place LIMIT order")

        print("\n--- PHASE 4: PortfolioService Live Stop Sync ---")
        from py_manage_portfolio.service import PortfolioService
        
        # Initialize service in live mode with our data source
        service = PortfolioService(project_root=parent_dir, context="live", data_source=ds)
        
        # We need a position in the state to update its stop
        # Mocking a position in the service state for testing
        from py_manage_portfolio.models.portfolio_state import PortfolioState, Position
        service.state = PortfolioState(
            timestamp=datetime.now().isoformat(),
            cash=10000.0,
            equity=10000.0,
            positions={
                "AAPL": Position(symbol="AAPL", quantity=10, entry_price=150.0, current_price=160.0)
            }
        )
        
        print("Setting first stop at 140.0...")
        service.update_stop_loss("AAPL", 140.0)
        time.sleep(2)
        
        orders = ds.get_open_orders(symbol="AAPL")
        stop_orders = [o for o in orders if o.order_type == "STP"]
        print(f"Found {len(stop_orders)} stop orders for AAPL.")
        for o in stop_orders:
            print(f"  Order: {o.order_id} price={o.stop_price} status={o.status}")
        
        if len(stop_orders) == 1 and stop_orders[0].stop_price == 140.0:
            print("✅ First stop correctly placed.")
            first_id = stop_orders[0].order_id
            
            print("\nUpdating stop to 145.0 (should cancel old and place new)...")
            service.update_stop_loss("AAPL", 145.0)
            time.sleep(3)
            
            orders = ds.get_open_orders(symbol="AAPL")
            stop_orders = [o for o in orders if o.order_type == "STP"]
            print(f"Found {len(stop_orders)} stop orders for AAPL.")
            for o in stop_orders:
                print(f"  Order: {o.order_id} price={o.stop_price} status={o.status}")
            
            if len(stop_orders) == 1 and stop_orders[0].stop_price == 145.0:
                 print("✅ Sync successful: Old stop cancelled, new one placed.")
            else:
                 print("❌ Sync failed or duplicate stops found!")
        else:
            print("❌ Initial stop placement failed.")

        print("\n--- PHASE 5: Modify Order ---")
        modify_symbol = "INTC"
        lmt_req = OrderRequest(
            symbol=modify_symbol,
            action="BUY",
            quantity=10,
            order_type="LMT",
            limit_price=1.0,
            time_in_force="DAY"
        )
        mod_id = ds.place_order(lmt_req)
        if mod_id:
            print(f"Placed order {mod_id} for {modify_symbol}")
            time.sleep(2)
            
            print(f"Modifying order {mod_id}: Quantity -> 20, Price -> 1.5")
            if ds.modify_order(mod_id, quantity=20, limit_price=1.5):
                time.sleep(2)
                orders = ds.get_open_orders(symbol=modify_symbol)
                target = next((o for o in orders if o.order_id == mod_id), None)
                if target and target.quantity == 20 and target.limit_price == 1.5:
                    print("✅ Order modification verified.")
                else:
                    print(f"❌ Modification failed to reflect in open orders: {target}")
            else:
                print("❌ modify_order reported failure.")
            
            print(f"Cleaning up order {mod_id}...")
            ds.cancel_order(mod_id)
            verify_order_gone(ds, mod_id)

        print("\n--- PHASE 6: Remove Stop Loss ---")
        # Reuse existing service from Phase 4 logic
        print("Placing stop at 150.0 for AAPL...")
        service.update_stop_loss("AAPL", 150.0)
        time.sleep(2)
        
        orders = ds.get_open_orders(symbol="AAPL")
        if any(o.order_type == "STP" and o.stop_price == 150.0 for o in orders):
            print("✅ Stop for AAPL confirmed.")
            stp_id = next(o.order_id for o in orders if o.order_type == "STP")
            
            print(f"Removing stop for AAPL...")
            service.remove_stop_loss("AAPL")
            time.sleep(2)
            
            if service.state.positions["AAPL"].stop_loss == 0.0:
                print("✅ Local state stop cleared.")
            else:
                print(f"❌ Local state stop NOT cleared: {service.state.positions['AAPL'].stop_loss}")
                
            verify_order_gone(ds, stp_id, "Broker Stop Order")
        else:
            print("❌ Failed to place initial stop for removal test.")

        print("\n--- PHASE 7: Stop-Limit Verification ---")
        # Reuse service for Stop-Limit
        print("Placing Stop-Limit for AAPL (Trigger 140, Limit 139)...")
        service.update_stop_loss("AAPL", 140.0, stop_type="STP LMT", limit_price=139.0)
        time.sleep(2)
        
        orders = ds.get_open_orders(symbol="AAPL")
        sl_order = next((o for o in orders if o.order_type == "STP LMT"), None)
        
        if sl_order and sl_order.stop_price == 140.0 and sl_order.limit_price == 139.0:
            print("✅ Stop-Limit order verified in broker.")
            # Verify local state
            pos = service.state.positions["AAPL"]
            if pos.stop_type == "STP LMT" and pos.stop_limit_price == 139.0:
                print("✅ Local state metadata verified.")
            else:
                print(f"❌ Local state metadata mismatch: {pos.stop_type}/{pos.stop_limit_price}")
            
            print("Cleaning up Stop-Limit...")
            ds.cancel_order(sl_order.order_id)
            verify_order_gone(ds, sl_order.order_id, "Stop-Limit Order")
        else:
            print(f"❌ Stop-Limit verification failed. Found: {sl_order}")

    finally:
        ds.disconnect()
        print("\nDisconnected from IBKR")

if __name__ == "__main__":
    test_order_management()
