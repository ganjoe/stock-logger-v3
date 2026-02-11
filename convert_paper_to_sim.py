import os
import xml.etree.ElementTree as ET
from datetime import datetime
from py_manage_portfolio.models.portfolio_state import PortfolioState, Position
from py_manage_portfolio.storage_manager import StorageManager

def migrate_paper_to_sim(project_root: str):
    """
    Migrates 'paper-trades.xml' into 'portfolio_simulation.json'.
    Reconstructs the portfolio state by replaying all trades.
    """
    trades_file = os.path.join(project_root, "paper-trades.xml")
    json_File = "data_portfolio_simulation.json"
    
    print(f"Migration: {trades_file} -> {json_File}")
    
    if not os.path.exists(trades_file):
        print("❌ paper-trades.xml not found. Nothing to migrate.")
        return

    # 1. Parse XML
    try:
        tree = ET.parse(trades_file)
        root = tree.getroot()
        trades = []
        for trade in root.findall("trade"):
            # Minimal parsing for migration
            try:
                t = {
                    "symbol": trade.find("symbol").text,
                    "quantity": float(trade.find("quantity").text),
                    "price": float(trade.find("price").text),
                    "date": trade.find("date").text
                }
                trades.append(t)
            except AttributeError:
                continue # Skip malformed
                
        print(f"Found {len(trades)} trades in XML.")
        
    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        return

    # 2. Replay Trades to build State
    # Start with empty state
    state = PortfolioState(
        timestamp=datetime.now().isoformat(),
        cash=100000.0, # Default starting cash we assume for paper
        equity=100000.0,
        positions={}
    )
    
    for t in trades:
        # Update State logic (simplified version of add_position)
        cost = t['quantity'] * t['price']
        state.cash -= cost
        
        pos = Position(
            symbol=t['symbol'], 
            quantity=t['quantity'], 
            entry_price=t['price'], 
            current_price=t['price'] # Assumption for migration
        )
        state.add_position(pos)
        
    # Recalculate Equity (Cash + MV)
    mv = sum(p.quantity * p.current_price for p in state.positions.values())
    state.equity = state.cash + mv
    state.update_timestamp()
    
    # 3. Save to JSON
    storage = StorageManager(os.path.join(project_root, "data"))
    storage.save_portfolio(state, json_File)
    
    print(f"✅ Migration Complete!")
    print(f"   Positions: {len(state.positions)}")
    print(f"   Cash: {state.cash:.2f}")
    print(f"   Equity: {state.equity:.2f}")
    print(f"Saved to: {os.path.join(storage.data_dir, json_File)}")

if __name__ == "__main__":
    migrate_paper_to_sim(".")
