import json
import os
import dataclasses
from typing import Optional
from .models.portfolio_state import PortfolioState, Position

class StorageManager:
    """Handles persistence of PortfolioState to JSON."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
    def _get_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def save_portfolio(self, state: PortfolioState, filename: str = "portfolio_simulation.json"):
        """Saves the portfolio state to a JSON file."""
        path = self._get_path(filename)
        data = dataclasses.asdict(state)
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
            
    def load_portfolio(self, filename: str = "portfolio_simulation.json") -> PortfolioState:
        """Loads the portfolio state from a JSON file. Returns empty state if file not found."""
        path = self._get_path(filename)
        
        if not os.path.exists(path):
            return self._create_empty_state()
            
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            # Reconstruct objects
            positions = {}
            for sym, pos_data in data.get('positions', {}).items():
                positions[sym] = Position(**pos_data)
                
            return PortfolioState(
                timestamp=data.get('timestamp', ''),
                cash=data.get('cash', 0.0),
                equity=data.get('equity', 0.0),
                positions=positions
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to load portfolio from {filename}: {e}")
            return self._create_empty_state()

    def _create_empty_state(self) -> PortfolioState:
        from datetime import datetime
        return PortfolioState(
            timestamp=datetime.now().isoformat(),
            cash=100000.0, # Default starting cash for simulation
            equity=100000.0,
            positions={}
        )
