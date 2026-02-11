"""
Full Integration Test for BrokerDataSource.

Tests the complete lifecycle:
1. Connection
2. Account Data Retrieval
3. Order Placement (Paper Mode)
4. Order Status Checking
5. Order Cancellation

Usage:
    pytest py_broker_captrader/test_broker_full_integration.py --run-live
"""
import pytest
import time
from py_broker_captrader.broker_data_source import BrokerDataSource
from py_manage_portfolio.data_source import OrderRequest, OrderStatus

@pytest.mark.skipif("not config.getoption('--run-live')", reason="Requires live broker connection")
class TestBrokerFullIntegration:
    
    @pytest.fixture(scope="class")
    def data_source(self):
        """Setup BrokerDataSource connected to TWS/Gateway."""
        # Config matches TWS default for Paper Trading
        ds = BrokerDataSource(host="127.0.0.1", port=4002, client_id=888, auto_connect=True)
        
        # Wait for connection
        timeout = 10
        start = time.time()
        while not ds.is_connected() and time.time() - start < timeout:
            time.sleep(0.5)
            
        if not ds.is_connected():
            pytest.fail("Could not connect to IBKR Gateway/TWS")
            
        yield ds
        
        ds.disconnect()

    def test_connection_and_account_data(self, data_source):
        """Verify connection and basic account metrics."""
        assert data_source.is_connected()
        
        # Give it a moment to sync account data
        time.sleep(2)
        
        metrics = data_source.get_account_metrics()
        print(f"\nAccount Metrics: {metrics}")
        
        assert metrics.equity > 0, "Equity should be positive"
        assert metrics.cash >= 0, "Cash should be non-negative"

    def test_order_lifecycle(self, data_source):
        """
        Test complete order lifecycle:
        Place -> Verify Open -> Cancel -> Verify Cancelled
        """
        symbol = "INTC"  # Intel usually liquid and cheap, good for tests
        
        # 1. Place Limit Buy Order deep OTM (Out of The Money) to avoid fill
        # Price: 1.00 USD (Assuming INTC is > $10)
        request = OrderRequest(
            symbol=symbol,
            action="BUY",
            quantity=1,
            order_type="LMT",
            limit_price=1.00,
            time_in_force="DAY"
        )
        
        print(f"\nPlacing Order: {request}")
        order_id = data_source.place_order(request)
        
        assert order_id is not None, "Order placement failed"
        print(f"Order Placed. ID: {order_id}")
        
        # 2. Wait for propagation
        time.sleep(2)
        
        # 3. Verify Order is Open
        open_orders = data_source.get_open_orders(symbol)
        found = False
        target_order = None
        
        # IBKR updates order IDs sometimes, but correlation should work
        # We look for our order by matching parameters or ID
        for o in open_orders:
            if o.order_id == order_id or (o.symbol == symbol and o.limit_price == 1.00 and o.quantity == 1):
                target_order = o
                found = True
                break
        
        assert found, f"Order {order_id} not found in open orders: {open_orders}"
        assert target_order.status in [OrderStatus.SUBMITTED, OrderStatus.PRE_SUBMITTED], \
            f"Unexpected status: {target_order.status}"
            
        print(f"Order Verified Open: {target_order}")
        
        # 4. Cancel Order
        print(f"Cancelling Order {order_id}...")
        cancelled = data_source.cancel_order(order_id)
        assert cancelled, "Cancel request failed"
        
        # 5. Verify Cancellation (Wait for update)
        time.sleep(2)
        
        # Fetch open orders again - it should be gone or marked cancelled
        open_orders_after = data_source.get_open_orders(symbol)
        is_active = False
        for o in open_orders_after:
             if o.order_id == order_id:
                 if o.status not in [OrderStatus.CANCELLED, OrderStatus.UNKNOWN]:
                     is_active = True
                     print(f"Order still active with status: {o.status}")
        
        assert not is_active, "Order should be cancelled or removed from open orders"
        print("Order Cancellation Verified.")

    def test_get_positions(self, data_source):
        """Verify position retrieval (Read-Only)."""
        positions = data_source.get_positions()
        print(f"\nPositions Found: {len(positions)}")
        for p in positions:
            print(f" - {p.symbol}: {p.quantity}")
        
        # Just ensure it returns a list, clean or empty
        assert isinstance(positions, list)
