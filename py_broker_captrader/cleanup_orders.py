import sys
import os
import time

# Add parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ib_insync import IB

def cleanup():
    ib = IB()
    print("Connecting as Master (Client 0) to find orders...")
    print("NOTE: Ensure the CLI is CLOSED or disconnected before running this.")
    try:
        ib.connect('127.0.0.1', 4002, clientId=0, timeout=10)
    except Exception as e:
        print(f"Master connection failed (already connected?): {e}")
        return

    ib.reqAllOpenOrders()
    trades = ib.openTrades()
    
    if not trades:
        print("No open orders found.")
        ib.disconnect()
        return

    targets = []
    for t in trades:
        targets.append({
            'symbol': t.contract.symbol,
            'clientId': t.order.clientId,
            'orderId': t.order.orderId,
            'permId': t.order.permId
        })
    
    ib.disconnect()
    
    for target in targets:
        print(f"\nTargeting: {target['symbol']} (Owner: {target['clientId']}, OrderId: {target['orderId']})")
        clean_ib = IB()
        try:
            print(f"Connecting as Client {target['clientId']}...")
            clean_ib.connect('127.0.0.1', 4002, clientId=target['clientId'])
            
            # Find the order in this session
            clean_ib.reqAllOpenOrders()
            session_trades = [t for t in clean_ib.openTrades() if t.order.permId == target['permId']]
            
            if session_trades:
                trade = session_trades[0]
                print(f"Found order in session. Cancelling...")
                clean_ib.cancelOrder(trade.order)
                time.sleep(2)
                print("Cancellation requested.")
            else:
                print(f"Could not find order {target['permId']} in session {target['clientId']}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            clean_ib.disconnect()

if __name__ == "__main__":
    cleanup()
