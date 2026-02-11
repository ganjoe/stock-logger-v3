import sys
import os
import random
from datetime import datetime
import time

# Add parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from py_broker_captrader.broker_data_source import BrokerDataSource

def debug_orders():
    # Use 0 if provided as arg, else random
    if len(sys.argv) > 1:
        client_id = int(sys.argv[1])
    else:
        client_id = 0
        
    print(f"DEBUG: Connecting with client_id: {client_id} to port 4002")
    
    ds = BrokerDataSource(host="127.0.0.1", port=4002, client_id=client_id, auto_connect=True)
    
    if not ds.is_connected():
        print("Failed to connect")
        return

    try:
        ib = ds._connection.ib
        ib.reqAllOpenOrders()
        trades = ib.openTrades()
        
        print(f"\nFound {len(trades)} open trades:")
        print(f"{'Sym':<6} {'Action':<6} {'Qty':<5} {'OrderId':<8} {'PermId':<12} {'ClientId':<10} {'Status':<15}")
        print("-" * 75)
        
        print("\nResults from ds.get_open_orders():")
        print(f"{'ID':<15} {'Sym':<6} {'Owner':<10} {'Status':<15}")
        print("-" * 50)
        
        open_orders = ds.get_open_orders()
        for oo in open_orders:
            # We can find the clientId by matching with the trades list
            if oo.order_id.startswith('p'):
                original_trade = next((t for t in trades if str(t.order.permId) == oo.order_id[1:]), None)
            else:
                original_trade = next((t for t in trades if str(t.order.orderId) == oo.order_id), None)
            
            owner_id = original_trade.order.clientId if original_trade else "???"
            print(f"{oo.order_id:<15} {oo.symbol:<6} {owner_id:<10} {oo.status.value:<15}")
            
        print("\nOur session client_id:", ds._connection.config.client_id)
        
        if open_orders:
            target = open_orders[0]
            print(f"\n--- TEST: Attempting to cancel {target.order_id} ---")
            # Auto-proceed if 'cancel' is in args
            if 'cancel' in sys.argv:
                success = ds.cancel_order(target.order_id)
                if success:
                    print("✅ ds.cancel_order returned True (Requested)")
                else:
                    print("❌ ds.cancel_order returned False (Blocked or Failed)")
                    
                print("Waiting 3 seconds for IBKR feedback...")
                time.sleep(3)
            else:
                print("Skipping cancellation test (use 'cancel' as second arg to run)")
        
    finally:
        ds.disconnect()
        print("\nDisconnected from IBKR")

if __name__ == "__main__":
    debug_orders()
