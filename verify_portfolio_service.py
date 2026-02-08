import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from py_manage_portfolio.service import PortfolioService

def test_service():
    print("Testing PortfolioService...")
    service = PortfolioService(project_root=".")
    
    print("\nFetching open positions...")
    positions = service.get_open_positions(update_prices=False)
    print(f"Found {len(positions)} open positions.")
    
    if positions:
        p = positions[0]
        print(f"Sample Position: {p.symbol} ({p.direction})")
        print(f"  Qty: {p.quantity}, Entry: {p.entry_price}, Mkt: {p.current_price}")
        print(f"  Unreal PL: {p.unrealized_pl} ({p.unrealized_pct}%)")
        print(f"  Flags: {p.status_flags}")

    print("\nFetching summary...")
    summary = service.get_summary()
    print(f"Summary Metrics:")
    print(f"  Total Invested: {summary.total_invested}")
    print(f"  Buying Power: {summary.buying_power}")
    print(f"  Equity: {summary.equity}")
    print(f"  Status: {summary.count_ok} OK, {summary.count_trail} Trail, {summary.count_missing} Missing")

    # BI-DIRECTIONAL TEST
    if positions:
        target = positions[0].symbol
        print(f"\n--- Testing Bi-Directional API for {target} ---")
        
        # 1. Update
        new_stop = positions[0].entry_price * 0.95
        print(f"Updating stop for {target} to {new_stop:.2f}...")
        res = service.update_stop_loss(target, new_stop)
        print(f"Update Result: {res}")
        
        # 2. Verify
        updated_pos = [p for p in service.get_open_positions() if p.symbol == target][0]
        print(f"Verified Stop: {updated_pos.stop_loss} (Expected: {new_stop:.2f})")
        
        # 3. Delete
        print(f"Deleting stop for {target}...")
        res = service.delete_stop_loss(target)
        print(f"Delete Result: {res}")
        
        # 4. Final check
        final_pos = [p for p in service.get_open_positions() if p.symbol == target][0]
        print(f"Final Status: {final_pos.status_flags} (Expected: Missing if it was OK before)")

if __name__ == "__main__":
    test_service()
