"""
Integration Tests for Broker Data Provider.

Tests data fetching logic with:
1. Mocked Connection (Mock Test)
2. Live Connection (Live Test - requires manual flag --run-live)
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from py_broker_captrader.data_provider import BrokerDataProvider, BarData
from py_broker_captrader.connection import IBKRConnection, ConnectionConfig

# Mock Data for T-009 Integration Test
MOCK_BARS = [
    MagicMock(date=datetime(2023, 1, 1), open=100.0, high=105.0, low=99.0, close=102.0, volume=1000),
    MagicMock(date=datetime(2023, 1, 2), open=102.0, high=104.0, low=101.0, close=103.0, volume=1500),
]

class TestBrokerDataProviderIntegration:
    
    @pytest.fixture
    def mock_connection(self):
        """Mocked IBKR Connection."""
        conn = MagicMock(spec=IBKRConnection)
        conn.is_connected.return_value = True
        conn.ib = MagicMock()
        return conn

    def test_fetch_history_mocked(self, mock_connection):
        """Verify request structure and response parsing (T-009 Mock)."""
        provider = BrokerDataProvider(mock_connection)
        
        # Setup Mock IB Behavior
        mock_connection.ib.qualifyContracts.return_value = [MagicMock()] # Success
        mock_connection.ib.reqHistoricalData.return_value = MOCK_BARS
        
        # Execute
        result = provider.get_daily_history("AAPL", days=10)
        
        # Verify
        assert len(result) == 2
        assert isinstance(result[0], BarData)
        assert result[0].close == 102.0
        assert result[1].volume == 1500.0
        
        # Verify call args
        mock_connection.ib.reqHistoricalData.assert_called_once()
        call_args = mock_connection.ib.reqHistoricalData.call_args
        assert call_args[1]['durationStr'] == '10 D'
        assert call_args[1]['barSizeSetting'] == '1 day'

    def test_fetch_batch_pacing_mocked(self, mock_connection):
        """Verify batch retrieval calls individual fetch sequentially."""
        provider = BrokerDataProvider(mock_connection)
        
        # Setup Mock
        mock_connection.ib.qualifyContracts.return_value = [MagicMock()]
        mock_connection.ib.reqHistoricalData.return_value = MOCK_BARS
        
        # Execute Batch
        symbols = ["AAPL", "MSFT"]
        with patch('time.sleep') as mock_sleep: # Don't actually sleep in test
            results = provider.get_batch_history(symbols, days=5)
        
        # Verify
        assert len(results) == 2
        assert "AAPL" in results
        assert "MSFT" in results
        assert mock_connection.ib.reqHistoricalData.call_count == 2

    @pytest.mark.skipif("not config.getoption('--run-live')", reason="Requires live broker connection")
    def test_live_fetch_aapl(self):
        """
        Manual Integration Test: Fetch AAPL from real Gateway.
        Run with: pytest tests/integration/test_broker_data_provider.py --run-live
        """
        # Connect to Gateway (Paper Port 4002 default)
        config = ConnectionConfig(port=4002, client_id=999) # Use unique ID
        conn = IBKRConnection(config)
        
        if not conn.connect():
             pytest.skip("Could not connect to IBKR Gateway")
             
        try:
            provider = BrokerDataProvider(conn)
            print("\nFetching Live AAPL Data...")
            data = provider.get_daily_history("AAPL", days=5)
            
            assert len(data) > 0
            latest = data[-1]
            print(f"Latest AAPL Bar: {latest.date} Close: {latest.close}")
            assert latest.close > 0
            
        finally:
            conn.disconnect()
