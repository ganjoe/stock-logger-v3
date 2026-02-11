import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from py_manage_portfolio.service import PortfolioService
from py_manage_portfolio.models.portfolio_state import Position

def verify_simulation():
    print("\n--- Testing Simulation Mode (Unified) ---")
    
    # 1. Init Service (Sim)
    # Ensure clean slate
    if os.path.exists("data/data_portfolio_simulation.json"):
        os.remove("data/data_portfolio_simulation.json")
        
    service = PortfolioService(project_root=".", context="sim")
    
    # 2. Load State (Should be empty or default)
    state = service.load_portfolio_state()
    print(f"Initial State: Cash={state.cash}, Equity={state.equity}, Positions={len(state.positions)}")
    
    # 3. Simulate a Trade (Add Position)
    print("Simulating Buy: 10x AAPL @ 150.00")
    new_pos = Position(symbol="AAPL", quantity=10, entry_price=150.00, current_price=155.00)
    
    # Update State Logic (normally this would be in a service method, simplified for test)
    state.cash -= (new_pos.quantity * new_pos.entry_price)
    state.add_position(new_pos)
    state.update_timestamp()
    
    # 4. Save
    print("Saving State...")
    service.save_simulation_state()
    
    # 5. Reload and Verify
    print("Reloading...")
    service2 = PortfolioService(project_root=".", context="sim")
    state2 = service2.load_portfolio_state()
    
    # Verify
    aapl = state2.positions.get("AAPL")
    if aapl and aapl.quantity == 10:
        print(f"✅ Position Persisted: {aapl}")
    else:
        print("❌ Position NOT Persisted!")
        
    if state2.cash == state.cash:
        print(f"✅ Cash Persisted: {state2.cash}")
    else:
        print(f"❌ Cash Mismatch: {state2.cash} != {state.cash}")
        
    # 6. Verify CLI Metrics
    eq, cash, exp = service2._get_journal_metrics()
    print(f"CLI Metrics: Eq={eq}, Cash={cash}, Exp={exp}")
    
    # 7. Verify Update Journal
    service2.update_paper_journal(equity=200000.0, exposure=50000.0)
    # Expect Cash = 150000
    if service2.state.cash == 150000.0:
         print("✅ Metrics Updated Successfully")
    # 9. Verify Data Source Accessor
    ds = service2.get_data_source()
    print(f"✅ get_data_source() works. Type: {type(ds).__name__}")
    
    # 10. Verify Clear Portfolio
    service2.clear_paper_portfolio()
    if service2.state.cash == 100000.0 and len(service2.state.positions) == 0:
        print("✅ clear_paper_portfolio() works.")
    else:
        print(f"❌ Clear Failed: Cash={service2.state.cash}, Pos={len(service2.state.positions)}")
         
    # 8. Verify Aliases (get_summary, get_risk_settings)
    try:
        summ = service2.get_summary()
        print(f"✅ get_summary() works. Equity={summ.equity}")
        
        risk = service2.get_risk_settings()
        print(f"✅ get_risk_settings() works. Max Risk={risk.get('max_equity_risk')}")
    except AttributeError as e:
        print(f"❌ Alias Check Failed: {e}")


def verify_live_connect():
    print("\n--- Testing Live Mode (Broker Integration) ---")
    try:
        from py_broker_captrader import BrokerDataSource
        
        # Connect to Broker (assuming it's running)
        print("Connecting to 4001...")
        ds = BrokerDataSource(host="127.0.0.1", port=4001, auto_connect=True)
        
        if ds.is_connected():
            print("Broker Connected.")
            
            # Init Service with Broker Source
            service = PortfolioService(project_root=".", context="live", data_source=ds)
            
            # Load State (Fetch from Broker)
            print("Fetching Portfolio State...")
            state = service.load_portfolio_state()
            
            print(f"✅ Fetched State: Cash={state.cash:.2f}, Equity={state.equity:.2f}")
            print(f"   Positions: {len(state.positions)}")
            
            # Verify Snapshot exists
            import os
            if os.path.exists("data/data_portfolio_live_snapshot.json"):
                print("✅ Live Snapshot Saved: data/data_portfolio_live_snapshot.json")
            else:
                print("❌ Live Snapshot NOT Saved!")
                
            for sym, pos in state.positions.items():
                print(f"   - {sym}: {pos.quantity} @ {pos.entry_price:.2f}")
                
            ds.disconnect()
        else:
            print("⚠️ Could not connect to broker (Skipping live test).")
            
    except ImportError:
        print("⚠️ Broker module not found (Skipping).")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error in Live Test: {e}")

if __name__ == "__main__":
    verify_simulation()
    # verification of live connect requires running gateway
    verify_live_connect() 
