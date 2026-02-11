"""
IBKR Broker DataSource Implementation.

Implements PortfolioReader + ConnectionAware + OrderManager directly.
No adapter layer needed — this IS the data source.
"""
from datetime import date, datetime
from typing import Dict, List, Optional

from py_manage_portfolio.data_source import (
    PortfolioReader, ConnectionAware, OrderManager,
    OrderRequest, OrderStatus, OpenOrder
)
from py_manage_portfolio.models.portfolio_state import PortfolioState, Position
from .connection import IBKRConnection, ConnectionConfig


class BrokerDataSource(PortfolioReader, ConnectionAware, OrderManager):
    """
    IBKR-based implementation of PortfolioReader + ConnectionAware + OrderManager.
    
    Connects to TWS/Gateway to fetch live portfolio data.
    Can be used directly as a data source by PortfolioService — no adapter needed.
    
    Args:
        host: TWS/Gateway host (default: 127.0.0.1)
        port: TWS/Gateway port (default: 7497)
        client_id: TWS Client ID (default: 1)
        account_id: Optional account ID for multi-account setups
        auto_connect: If True, connect immediately on init
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1,
                 account_id: Optional[str] = None, auto_connect: bool = True):
        config = ConnectionConfig(host=host, port=port, client_id=client_id)
        self._connection = IBKRConnection(config)
        self._account_id = account_id
        
        if auto_connect:
            self._connection.connect()
            # Force delayed data (3) to avoid data subscription costs
            self._connection.ib.reqMarketDataType(3)
            # Request all open orders (including those manually placed in TWS)
            self._connection.ib.reqAllOpenOrders()
            self._connection.ib.reqAutoOpenOrders(True)
    
    def _get_account(self) -> str:
        """Get the account ID to use for API calls."""
        if self._account_id:
            return self._account_id
        
        # Auto-detect first managed account
        accounts = self._connection.ib.managedAccounts()
        if not accounts:
            raise ValueError("No managed accounts found")
        return accounts[0]
    
    # --- PortfolioReader ---
    
    def get_portfolio_state(self) -> PortfolioState:
        """
        Syncs full portfolio state from Broker and returns a PortfolioState.
        Includes Cash, Equity, Positions, and Stop-Loss Levels.
        """
        if not self.is_connected():
            return PortfolioState(
                timestamp=datetime.now().isoformat(),
                cash=0.0,
                equity=0.0,
                positions={}
            )
            
        ib = self._connection.ib
        account = self._get_account()
        
        # 1. Account Metrics
        account_data = self._get_account_summary()
        cash = account_data.get('AvailableFunds', 0.0)
        equity = account_data.get('NetLiquidation', 0.0)
        
        # 2. Portfolio Items
        portfolio_items = ib.portfolio(account)
        
        # 3. Active Stops
        stops = self._get_active_stops()
        
        positions = {}
        for item in portfolio_items:
            contract = item.contract
            qty = float(item.position)
            if qty == 0:
                continue
            
            avg_cost_per_share = float(item.averageCost)
            market_price = float(item.marketPrice) if item.marketPrice else 0.0
            
            # Create Position
            pos = Position(
                symbol=contract.symbol,
                quantity=abs(qty),
                entry_price=avg_cost_per_share,
                current_price=market_price,
                currency=contract.currency,
                direction="SHORT" if qty < 0 else "LONG"
            )
            
            # Enrich with stop if available
            if contract.symbol in stops:
                pos.stop_loss = stops[contract.symbol]
            
            positions[contract.symbol] = pos
            
        return PortfolioState(
            timestamp=datetime.now().isoformat(),
            cash=cash,
            equity=equity,
            positions=positions
        )

    def _get_account_summary(self) -> Dict[str, float]:
        """Fetch account summary (NetLiquidation, AvailableFunds)."""
        ib = self._connection.ib
        account = self._get_account()
        
        ib.reqAccountSummary()
        # Sleep slightly to allow data to arrive? 
        # ib_insync usually handles this if we wait for the req?
        # Actually accountSummary returns a list, it might block?
        # Let's rely on it returning data or use values from cache if subscribed
        summary_list = ib.accountSummary(account)
        
        values = {}
        target_tags = {'NetLiquidation', 'AvailableFunds'}
        for item in summary_list:
            if item.account == account and item.tag in target_tags:
                try:
                    values[item.tag] = float(item.value)
                except ValueError:
                    pass
        return values

    def _get_active_stops(self) -> Dict[str, float]:
        """Fetch active stop orders (STP, STP LMT, TRAIL) keyed by symbol."""
        ib = self._connection.ib
        stops = {}
        trades = ib.openTrades()
        
        for trade in trades:
            order = trade.order
            contract = trade.contract

            # 1. Classical Stop orders
            if order.orderType in ('STP', 'STP LMT'):
                 if order.auxPrice and order.auxPrice < 1.0e300:
                     stops[contract.symbol] = float(order.auxPrice)
            
            # 2. Trailing Stop orders
            elif order.orderType in ('TRAIL', 'TRAIL LIMIT'):
                # For trailing stops, the current stop price is in trailStopPrice
                if hasattr(order, 'trailStopPrice') and order.trailStopPrice and order.trailStopPrice < 1.0e300:
                    stops[contract.symbol] = float(order.trailStopPrice)
                elif order.auxPrice and order.auxPrice < 1.0e300:
                    # Fallback or initialization
                    stops[contract.symbol] = float(order.auxPrice)
        
        print(f"DEBUG: Resolved Stops: {stops}")
        return stops
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OpenOrder]:
        """Get all open orders from IBKR."""
        ib = self._connection.ib
        trades = ib.openTrades()
        
        result = []
        for trade in trades:
            order = trade.order
            contract = trade.contract
            
            if symbol and contract.symbol != symbol:
                continue
                
            # Filter prices: 1.7e308 or similar high values
            lmt_price = float(order.lmtPrice) if order.lmtPrice and order.lmtPrice < 1.0e300 else None
            stp_price = float(order.auxPrice) if order.auxPrice and order.auxPrice < 1.0e300 else None
            
            # Map status
            status_str = trade.orderStatus.status
            status = OrderStatus.UNKNOWN
            
            if status_str in ('Submitted', 'PendingSubmit', 'PreSubmitted', 'ApiPending'):
                 status = OrderStatus.SUBMITTED if status_str == 'Submitted' else OrderStatus.PRE_SUBMITTED
            elif status_str == 'Filled': 
                status = OrderStatus.FILLED
            elif status_str in ('Cancelled', 'ApiCancelled', 'Inactive'): 
                status = OrderStatus.CANCELLED
            else:
                print(f"⚠️ Unknown IBKR Order Status: {status_str}")
                status = OrderStatus.UNKNOWN
            
            result.append(OpenOrder(
                symbol=contract.symbol,
                order_type=order.orderType,
                action=order.action,
                quantity=float(order.totalQuantity),
                filled_quantity=float(trade.orderStatus.filled),
                status=status,
                limit_price=lmt_price,
                stop_price=stp_price,
                time_in_force=order.tif,
                order_id=str(order.orderId)
            ))
        
        return result

    def place_order(self, request: OrderRequest) -> Optional[str]:
        """Places a new order at the broker."""
        ib = self._connection.ib
        try:
            from ib_insync import Contract, Order
            
            # Create Contract
            contract = Contract()
            contract.symbol = request.symbol
            contract.secType = 'STK'
            contract.exchange = 'SMART'
            contract.currency = 'USD'
            
            # Qualify to get conId
            ib.qualifyContracts(contract)
            
            # Create Order
            order = Order()
            order.action = request.action # 'BUY' or 'SELL'
            order.totalQuantity = request.quantity
            order.orderType = request.order_type # 'LMT', 'MKT', 'STP'
            order.tif = request.time_in_force
            
            if request.limit_price and request.limit_price > 0:
                order.lmtPrice = request.limit_price
            
            if request.stop_price and request.stop_price > 0:
                order.auxPrice = request.stop_price
                
            # Place
            trade = ib.placeOrder(contract, order)
            return str(trade.order.orderId)
            
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an order by ID."""
        ib = self._connection.ib
        try:
            target_trade = None
            for trade in ib.openTrades():
                if str(trade.order.orderId) == str(order_id):
                    target_trade = trade
                    break
            
            if not target_trade:
                for order in ib.orders():
                     if str(order.orderId) == str(order_id):
                         ib.cancelOrder(order)
                         return True
                return False

            ib.cancelOrder(target_trade.order)
            return True
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return False



    # --- ConnectionAware ---
    
    def disconnect(self) -> None:
        """Close the broker connection."""
        self._connection.disconnect()
    
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connection.is_connected()
