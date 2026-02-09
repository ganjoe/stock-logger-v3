"""
IBKR Broker DataSource Implementation.

Implements PortfolioDataSource for IBKR/CapTrader broker.
"""
from datetime import date
from typing import Dict, List, Optional

from py_manage_portfolio.data_source import (
    PortfolioDataSource,
    AccountMetrics,
    RawPosition,
    StopOrder
)
from .connection import IBKRConnection, ConnectionConfig


class BrokerDataSource(PortfolioDataSource):
    """
    IBKR-based implementation of PortfolioDataSource.
    
    Connects to TWS/Gateway to fetch live portfolio data.
    
    Args:
        host: TWS/Gateway host (default: 127.0.0.1)
        port: TWS/Gateway port (default: 7497)
        account_id: Optional account ID for multi-account setups
        auto_connect: If True, connect immediately on init
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497,
                 account_id: Optional[str] = None, auto_connect: bool = True):
        config = ConnectionConfig(host=host, port=port)
        self._connection = IBKRConnection(config)
        self._account_id = account_id
        
        if auto_connect:
            self._connection.connect()
    
    def _get_account(self) -> str:
        """Get the account ID to use for API calls."""
        if self._account_id:
            return self._account_id
        
        # Auto-detect first managed account
        accounts = self._connection.ib.managedAccounts()
        if not accounts:
            raise ValueError("No managed accounts found")
        return accounts[0]
    
    def get_positions(self) -> List[RawPosition]:
        """Get open positions from IBKR."""
        ib = self._connection.ib
        positions = ib.positions(self._get_account())
        
        result = []
        for pos in positions:
            contract = pos.contract
            result.append(RawPosition(
                symbol=contract.symbol,
                isin=None,  # IBKR doesn't expose ISIN directly
                quantity=float(pos.position),
                entry_price=float(pos.avgCost) / float(pos.position) if pos.position else 0,
                entry_date=None,  # Not available via positions API
                currency=contract.currency
            ))
        
        return result
    
    def get_stop_losses(self) -> Dict[str, StopOrder]:
        """Get active stop orders from IBKR."""
        ib = self._connection.ib
        orders = ib.openOrders()
        
        result = {}
        for trade in ib.openTrades():
            order = trade.order
            contract = trade.contract
            
            # Only include STP (stop) and STP LMT (stop limit) orders
            if order.orderType in ('STP', 'STP LMT'):
                result[contract.symbol] = StopOrder(
                    symbol=contract.symbol,
                    stop_price=float(order.auxPrice),
                    order_id=str(order.orderId)
                )
        
        return result
    
    def get_account_metrics(self) -> AccountMetrics:
        """Get account summary from IBKR."""
        ib = self._connection.ib
        account = self._get_account()
        
        # Request account values
        ib.reqAccountSummary()
        ib.sleep(1)  # Wait for data
        
        summary = ib.accountSummary(account)
        
        # Extract relevant values
        values = {item.tag: float(item.value) for item in summary if item.account == account}
        
        return AccountMetrics(
            equity=values.get('NetLiquidation', 0.0),
            cash=values.get('AvailableFunds', 0.0),
            exposure=values.get('GrossPositionValue', 0.0)
        )
    
    def set_stop_loss(self, symbol: str, stop_price: float) -> bool:
        """
        Place or modify a stop-loss order at the broker.
        
        Note: This creates a new STP order or modifies existing one.
        """
        ib = self._connection.ib
        
        try:
            from ib_insync import Stock, StopOrder as IB_StopOrder
            
            # Check if we have an existing stop for this symbol
            existing_stops = self.get_stop_losses()
            
            if symbol in existing_stops:
                # Modify existing order
                order_id = int(existing_stops[symbol].order_id)
                # Cancel and replace (IBKR doesn't support simple price modification)
                for trade in ib.openTrades():
                    if trade.order.orderId == order_id:
                        ib.cancelOrder(trade.order)
                        break
            
            # Create new stop order
            contract = Stock(symbol, 'SMART', 'USD')
            ib.qualifyContracts(contract)
            
            # Determine quantity from current position
            positions = ib.positions(self._get_account())
            qty = 0
            for pos in positions:
                if pos.contract.symbol == symbol:
                    qty = abs(pos.position)
                    break
            
            if qty == 0:
                return False
            
            order = IB_StopOrder('SELL', qty, stop_price)
            trade = ib.placeOrder(contract, order)
            
            return trade is not None
            
        except Exception as e:
            print(f"Error setting stop loss: {e}")
            return False
    
    def close_position(self, symbol: str) -> bool:
        """
        Close a position by placing a market order.
        
        Note: This places an actual order at the broker!
        """
        raise NotImplementedError(
            "close_position not supported in BrokerDataSource. "
            "Use broker interface directly for order execution."
        )
    
    def add_position(self, symbol: str, entry_price: float, stop_loss: float,
                     quantity: float, **kwargs) -> dict:
        """Not supported for broker - would require actual order placement."""
        raise NotImplementedError(
            "add_position not supported in BrokerDataSource. "
            "Use broker interface directly for order execution."
        )
    
    def disconnect(self):
        """Close the broker connection."""
        self._connection.disconnect()
    
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connection.is_connected()
