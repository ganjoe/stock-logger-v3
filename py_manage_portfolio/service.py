import os
import json
from datetime import datetime
from typing import Dict, Optional, Tuple, List

from .models.portfolio_state import PortfolioState, Position, PortfolioSummary
from .storage_manager import StorageManager
from .data_source import PortfolioReader, ConnectionAware

from py_datafetcher.service import DataFetcherService
# Legacy support for Dashboard (XML/CSV logging) is handled via appending to files,
# but NOT reading from them for state.

class PortfolioService:
    def __init__(self, project_root: str, context: str = "live", 
                 data_source: Optional[PortfolioReader] = None):
        """
        Unified Portfolio Service.
        - context="live": Source of Truth is Broker (via data_source), fallback to snapshot.
        - context="sim": Source of Truth is local JSON (via StorageManager).
        
        Args:
            data_source: Optional broker data source. None = offline/snapshot mode.
        """
        self.project_root = os.path.abspath(project_root)
        self.context = context.lower()
        if self.context == "paper": self.context = "sim"
        
        self.data_fetcher = DataFetcherService()
        self.storage = StorageManager(os.path.join(self.project_root, "data"))
        
        # Broker data source (None = offline/snapshot mode)
        self._data_source: Optional[PortfolioReader] = data_source
        
        # State
        self.state: Optional[PortfolioState] = None

    def load_portfolio_state(self) -> PortfolioState:
        """Loads the current portfolio state from the appropriate source."""
        snapshot_name = "data_portfolio_live_snapshot.json" if self.context == "live" else "data_portfolio_simulation.json"
        
        cached_state = None
        try:
            cached_state = self.storage.load_portfolio(snapshot_name)
        except Exception:
            pass

        if self.context == "sim":
            self.state = cached_state or PortfolioState(
                timestamp=datetime.now().isoformat(),
                cash=100000.0,
                equity=100000.0
            )
            return self.state
        
        # Live: try broker first, fall back to snapshot
        if self.is_broker_connected():
            try:
                fresh_state = self._data_source.get_portfolio_state()
                # Merge with local metadata (stops, ISINs, etc.)
                self.state = self._merge_states(fresh_state, cached_state)
                self.storage.save_portfolio(self.state, "data_portfolio_live_snapshot.json")
                return self.state
            except Exception as e:
                print(f"⚠️ Broker error: {e}")
                print("  Loading cached snapshot...")
        
        # Fallback to snapshot
        self.state = cached_state or PortfolioState(
            timestamp=datetime.now().isoformat(),
            cash=0.0,
            equity=0.0
        )
        return self.state
    
    def _merge_states(self, fresh: PortfolioState, cached: Optional[PortfolioState]) -> PortfolioState:
        """Merges fresh broker data with local metadata from cached snapshot."""
        if not cached:
            return fresh
            
        for symbol, new_pos in fresh.positions.items():
            if symbol in cached.positions:
                old_pos = cached.positions[symbol]
                # Preserve manual metadata if missing in broker data
                # Always merge metadata if price matches or broker has no stop
                if old_pos.stop_loss and (new_pos.stop_loss is None or new_pos.stop_loss == 0 or abs(new_pos.stop_loss - old_pos.stop_loss) < 0.05):
                    new_pos.stop_type = getattr(old_pos, 'stop_type', 'STP')
                    new_pos.stop_limit_price = getattr(old_pos, 'stop_limit_price', None)
                    if new_pos.stop_loss is None or new_pos.stop_loss == 0:
                        new_pos.stop_loss = old_pos.stop_loss
                if not new_pos.isin:
                    new_pos.isin = old_pos.isin
                if not new_pos.entry_date:
                    new_pos.entry_date = old_pos.entry_date
                if new_pos.initial_risk is None or new_pos.initial_risk == 0:
                    new_pos.initial_risk = old_pos.initial_risk
                    
        return fresh
    
    def is_broker_connected(self) -> bool:
        """Check if a broker data source is connected."""
        if self._data_source is None:
            return False
        if isinstance(self._data_source, ConnectionAware):
            return self._data_source.is_connected()
        return False

    def save_simulation_state(self):
        """Saves current state to JSON (only for Simulation)."""
        if self.context == "sim" and self.state:
            self.storage.save_portfolio(self.state, "data_portfolio_simulation.json")

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Returns the summary of the current portfolio state."""
        positions = self.get_positions()  # triggers load + enrichment
        
        total_invested = sum(p.quantity * p.entry_price for p in positions)
        current_equity = self.state.equity
        if self.context == "sim":
            market_value = sum(p.market_value for p in positions)
            current_equity = self.state.cash + market_value
        
        # Risk = sum of (current_price - stop_loss) * quantity for all positions with stops
        total_risk = sum(
            abs(p.current_price - p.stop_loss) * p.quantity
            for p in positions if p.stop_loss
        )
        
        # Status counters
        count_ok = sum(1 for p in positions if "OK" in p.status_flags or "Trail" in p.status_flags)
        count_warning = sum(1 for p in positions if "⏳" in p.status_flags or "⚠Loss" in p.status_flags)
        count_danger = sum(1 for p in positions if "🚨Stop" in p.status_flags or "❌NoStop" in p.status_flags)
        
        return PortfolioSummary(
            total_invested=total_invested,
            total_unrealized_pl=sum(p.unrealized_pnl for p in positions),
            total_risk=total_risk,
            buying_power=self.state.cash,
            equity=current_equity,
            position_count=len(positions),
            count_ok=count_ok,
            count_warning=count_warning,
            count_danger=count_danger,
        )

    def get_positions(self) -> List[Position]:
        """Returns list of Position objects, enriched with computed metrics."""
        if not self.state:
            self.load_portfolio_state()
        
        positions = list(self.state.positions.values())
        equity = self.state.equity
        if self.context == "sim":
            equity = self.state.cash + sum(p.market_value for p in positions)
        
        for p in positions:
            self._enrich_position(p, equity)
        
        return positions

    def _enrich_position(self, p: Position, equity: float):
        """Injects computed metrics into a Position object."""
        # Days held
        if p.entry_date:
            try:
                entry = datetime.strptime(p.entry_date, "%Y-%m-%d").date()
                p.days_held = (datetime.now().date() - entry).days
            except ValueError:
                p.days_held = 0
        
        # Position size as % of equity
        if equity > 0:
            p.pos_pct = (p.market_value / equity) * 100
        
        # Stop-based metrics
        if p.stop_loss and p.stop_loss > 0:
            # Initial risk per share
            p.initial_risk = abs(p.entry_price - p.stop_loss) * p.quantity
            
            # Distance from current price to stop (%)
            if p.current_price > 0:
                if p.direction == "SHORT":
                    p.dist_pct = ((p.stop_loss - p.current_price) / p.current_price) * 100
                else:
                    p.dist_pct = ((p.current_price - p.stop_loss) / p.current_price) * 100
            
            # Risk as % of equity
            if equity > 0:
                risk_amount = abs(p.current_price - p.stop_loss) * p.quantity
                p.risk_pct = (risk_amount / equity) * 100
        
        # Status flags
        p.status_flags = self._compute_status_flags(p)

    @staticmethod
    def _compute_status_flags(p: Position) -> List[str]:
        """Compute Minervini-style status flags for a position."""
        flags = []
        
        # Stop-loss check
        if not p.stop_loss or p.stop_loss <= 0:
            flags.append("❌NoStop")
            return flags  # Can't evaluate further without stop
        
        # P&L-based
        pnl_pct = p.unrealized_pct or 0.0
        if pnl_pct >= 0:
            # In profit — check if stop is trailing (above entry)
            if p.direction == "LONG" and p.stop_loss >= p.entry_price:
                flags.append("Trail")
            elif p.direction == "SHORT" and p.stop_loss <= p.entry_price:
                flags.append("Trail")
            else:
                flags.append("OK")
        else:
            # In loss
            flags.append("⚠Loss")
        
        # Holding duration warning (>30 days without significant gain)
        if p.days_held > 30 and pnl_pct < 5.0:
            flags.append("⏳")
        
        # Stop broken (price below stop for LONG, above for SHORT)
        if p.direction == "LONG" and p.current_price < p.stop_loss:
            flags.append("🚨Stop")
        elif p.direction == "SHORT" and p.current_price > p.stop_loss:
            flags.append("🚨Stop")
        
        return flags

    def add_position_sim(self, symbol: str, quantity: float, price: float, date: str) -> bool:
        """Adds a position in Simulation mode and updates unified state + legacy logs."""
        if self.context != "sim":
            raise ValueError("Cannot add simulated position in Live mode")
            
        # 1. Update State
        new_pos = Position(symbol=symbol, quantity=quantity, entry_price=price, current_price=price)
        if not self.state: self.load_portfolio_state()
        
        cost = quantity * price
        if self.state.cash >= cost:
            self.state.cash -= cost
            self.state.add_position(new_pos)
            self.state.update_timestamp()
            self.save_simulation_state()
            print(f"✅ Simulation: {quantity} {symbol} bought @ {price}")
            return True
        else:
            print("❌ Insufficient Cash for Simulation")
            return False

    def get_open_positions(self, update_prices: bool = False) -> List[Position]:
        """Alias for get_positions, compatible with CLI."""
        if update_prices and self.context == "live" and self.is_broker_connected():
             # IB needs a fraction of a second to update the portfolio list 
             # after an order execution event.
             # Use the data source's sync method to allow event loop ticks.
             ds = self.get_data_source()
             if hasattr(ds, 'sync'):
                 ds.sync(0.5)
             
             # Force refresh from data source
             self.load_portfolio_state()
        return self.get_positions()

    def update_stop_loss(self, symbol: str, stop_loss: float, 
                        stop_type: str = "STP", limit_price: Optional[float] = None,
                        quantity: Optional[float] = None, direction: Optional[str] = None):
        """
        Updates stop loss for a position.
        1. Persists to local snapshot (if position exists).
        2. Synchronizes with broker (if in live mode).
        """
        if not self.state: self.load_portfolio_state()
        
        pos = self.state.positions.get(symbol)
        if pos:
            pos.stop_loss = stop_loss 
            pos.stop_type = stop_type
            pos.stop_limit_price = limit_price
            
            # Recalculate initial risk if it's the first time setting a stop
            if not pos.initial_risk or pos.initial_risk == 0:
                pos.initial_risk = abs(pos.entry_price - stop_loss) * pos.quantity
            
            # 1. Persist locally (always)
            snapshot_name = "data_portfolio_live_snapshot.json" if self.context == "live" else "data_portfolio_simulation.json"
            self.storage.save_portfolio(self.state, snapshot_name)
            
            # Capture defaults for broker sync if not provided
            if quantity is None: quantity = pos.quantity
            if direction is None: direction = pos.direction
        
        # 2. Synchronize with Broker (if Live)
        if self.context == "live" and self.is_broker_connected():
            from .data_source import OrderManager, OrderRequest
            if isinstance(self._data_source, OrderManager):
                # We need quantity and direction for the broker order.
                # If these are missing (e.g. symbol not in portfolio and not passed), we can't sync.
                if quantity is None or direction is None:
                    print(f"⚠️ Cannot sync stop for {symbol} with broker: Position unknown and no quantity/direction provided.")
                    return

                print(f"📡 Syncing {stop_type} for {symbol} with Broker...")
                ds = self._data_source
                
                try:
                    # Cancel existing stops for this symbol
                    open_orders = ds.get_open_orders(symbol=symbol)
                    for o in open_orders:
                        if o.order_type in ['STP', 'STP LMT', 'TRAIL']:
                            print(f"   Cancelling existing stop order {o.order_id}...")
                            ds.cancel_order(o.order_id)
                    
                    # Place new stop order
                    action = "SELL" if direction == "LONG" else "BUY"
                    req = OrderRequest(
                        symbol=symbol,
                        action=action,
                        quantity=quantity,
                        order_type=stop_type,
                        limit_price=limit_price,
                        stop_price=stop_loss,
                        time_in_force="GTC"
                    )
                    
                    new_id = ds.place_order(req)
                    if new_id:
                        print(f"   ✅ Live {stop_type} placed! ID: {new_id}")
                    else:
                        print(f"   ❌ Failed to place live {stop_type} order.")
                        
                except Exception as e:
                    print(f"   ❌ Error syncing stop with broker: {e}")

        if self.context == "live" and pos:
            print(f"✓ Stop Loss for {symbol} saved to local snapshot.")

    def remove_stop_loss(self, symbol: str):
        """Removes stop loss for a position and cancels corresponding broker orders."""
        if not self.state: self.load_portfolio_state()
        
        if symbol in self.state.positions:
            pos = self.state.positions[symbol]
            pos.stop_loss = 0.0
            
            # 1. Persist locally
            snapshot_name = "data_portfolio_live_snapshot.json" if self.context == "live" else "data_portfolio_simulation.json"
            self.storage.save_portfolio(self.state, snapshot_name)
            
            # 2. Synchronize with Broker (if Live)
            from .data_source import OrderManager
            if self.context == "live" and self.is_broker_connected() and isinstance(self._data_source, OrderManager):
                print(f"📡 Removing Stop Loss for {symbol} at Broker...")
                ds = self._data_source
                try:
                    open_orders = ds.get_open_orders(symbol=symbol)
                    for o in open_orders:
                        if o.order_type in ['STP', 'STP LMT', 'TRAIL']:
                            print(f"   Cancelling existing stop order {o.order_id}...")
                            ds.cancel_order(o.order_id)
                except Exception as e:
                    print(f"   ❌ Error cancelling stop with broker: {e}")
            
            print(f"✓ Stop Loss for {symbol} removed.")

    def delete_position_sim(self, symbol: str):
        """Deletes a position in Simulation mode."""
        if self.context != "sim":
            raise ValueError("Delete allowed only in Simulation mode")
            
        if not self.state: self.load_portfolio_state()
        
        if symbol in self.state.positions:
            del self.state.positions[symbol]
            self.state.update_timestamp()
            self.save_simulation_state()
            print(f"🗑 Deleted {symbol} from Simulation")

    def update_paper_quantity(self, symbol: str, quantity: float):
        """Updates quantity in Simulation mode (Legacy Name: update_paper_quantity)."""
        if self.context != "sim":
             raise ValueError("Update allowed only in Simulation mode")
             
        if not self.state: self.load_portfolio_state()
        
        if symbol in self.state.positions:
            self.state.positions[symbol].quantity = quantity
            self.state.update_timestamp()
            self.save_simulation_state()
            print(f"✅ Updated quantity for {symbol} to {quantity}")

    def init_from_live(self):
        """Initializes Simulation state from current Live Broker state."""
        if self.context != "sim":
            raise ValueError("Can only init FROM live INTO sim context")
            
        try:
            from py_broker_captrader import BrokerDataSource
            
            print("Connecting to Broker to fetch Live Snapshot...")
            ds = BrokerDataSource(host="127.0.0.1", port=4001, client_id=999)
            if ds.is_connected():
                live_state = ds.get_portfolio_state()
                ds.disconnect()
                
                # 2. Overwrite Local State
                self.state = live_state
                self.state.update_timestamp()
                
                # 3. Save
                self.save_simulation_state()
                print("✅ Imported Live Portfolio to Simulation")
            else:
                print("⚠️ Could not connect to Broker.")
        except Exception as e:
            print(f"❌ Import failed: {e}")

    def _get_journal_metrics(self) -> Tuple[float, float, float]:
        """
        Returns (Equity, Cash, Exposure) for the CLI Wizard.
        Compatible with legacy _get_journal_metrics signature.
        """
        if not self.state: self.load_portfolio_state()
        
        # Calculate Exposure (Market Value of Positions)
        exposure = sum(p.quantity * p.current_price for p in self.state.positions.values())
        
        # Equity
        equity = self.state.equity
        if self.context == "sim":
             # In Sim, we might want to recalculate equity based on current prices if they changed
             equity = self.state.cash + exposure
             
        return equity, self.state.cash, exposure

    def update_paper_journal(self, equity: float, exposure: float):
        """
        Updates Simulation state based on manual Equity/Exposure input.
        Reverse engineers Cash = Equity - Exposure.
        """
        if self.context != "sim":
            raise ValueError("Update allowed only in Simulation mode")
            
        if not self.state: self.load_portfolio_state()
        
        # Derive Cash
        new_cash = equity - exposure
        
        self.state.cash = new_cash
        self.state.equity = equity
        self.state.update_timestamp()
        
        self.save_simulation_state()
        print(f"✅ Updated Simulation: Equity={equity:.2f}, Cash={new_cash:.2f}")

    def get_summary(self) -> PortfolioSummary:
        """Alias for get_portfolio_summary."""
        return self.get_portfolio_summary()

    def get_risk_settings(self) -> Dict[str, float]:
        """Returns risk settings (stub for CLI compatibility)."""
        # TODO: Load from config.json or similar
        return {
            "max_pos_size_pct": 25.0
        }

    def get_data_source(self):
        """Returns the current data source instance (may be None if offline)."""
        return self._data_source

    def set_data_source(self, data_source: Optional[PortfolioReader]):
        """Sets a new data source (or None to go offline)."""
        self._data_source = data_source
        # Reload state from new source
        self.load_portfolio_state()
    
    def disconnect_broker(self):
        """Disconnect broker and switch to snapshot mode."""
        if self._data_source and isinstance(self._data_source, ConnectionAware):
            self._data_source.disconnect()
        self._data_source = None
        self.load_portfolio_state()  # loads from snapshot

    def clear_paper_portfolio(self):
        """Resets the simulation portfolio to default state."""
        if self.context != "sim":
             raise ValueError("Clear allowed only in Simulation mode")
             
        # Create default empty state
        from datetime import datetime
        # Default starting cash? 100k or keep current?
        # Usually reset implies Start Over -> 100k
        self.state = PortfolioState(
            timestamp=datetime.now().isoformat(),
            cash=100000.0,
            equity=100000.0,
            positions={}
        )
        self.save_simulation_state()
        print("✅ Simulation Portfolio reset to Default (100k Cash).")

