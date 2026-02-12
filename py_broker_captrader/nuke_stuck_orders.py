import sys
import os
import time
from ib_insync import IB

# Add parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def nuke_orders():
    """
    Connects as Master (Client 0) to find all open orders, 
    then connects as the specific owners to cancel them.
    """
    port = 4002
    ib = IB()
    
    print(f"Connecting as Master (Client 0) to port {port}...")
    try:
        ib.connect('127.0.0.1', port, clientId=0, timeout=10)
    except Exception as e:
        print(f"❌ Master connection failed: {e}")
        print("💡 Make sure other tools (like the CLI or Dashboard) are disconnected from Client 0.")
        return

    ib.reqAllOpenOrders()
    trades = ib.openTrades()
    
    if not trades:
        print("✅ No open orders found across any Client IDs.")
        ib.disconnect()
        return

    print(f"Found {len(trades)} open orders.")
    
    # Collect unique client IDs and their orders
    id_map = {}
    for t in trades:
        cid = t.order.clientId
        if cid not in id_map:
            id_map[cid] = []
        id_map[cid].append(t)
    
    ib.disconnect()
    
    # Now connect for each client ID and cancel its orders
    for cid, items in id_map.items():
        print(f"\n--- Processing Client ID: {cid} ---")
        clean_ib = IB()
        try:
            clean_ib.connect('127.0.0.1', port, clientId=cid)
            clean_ib.reqAllOpenOrders()
            
            # Match current session's trades with the ones we found earlier
            # We use permId because it's unique and stable across connections
            perm_ids = [t.order.permId for t in items]
            session_trades = [t for t in clean_ib.openTrades() if t.order.permId in perm_ids]
            
            for t in session_trades:
                print(f"  🔥 Cancelling: {t.contract.symbol} (PermID: {t.order.permId}) ...")
                clean_ib.cancelOrder(t.order)
                time.sleep(1)
            
            time.sleep(1)
            print(f"  ✅ Finished Client ID {cid}")
            
        except Exception as e:
            print(f"  ❌ Error for Client ID {cid}: {e}")
        finally:
            if clean_ib.isConnected():
                clean_ib.disconnect()

    print("\n🏁 Nuke operation complete.")

if __name__ == "__main__":
    nuke_orders()
