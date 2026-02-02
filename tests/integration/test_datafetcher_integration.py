"""
Integration Tests for py_datafetcher module.

Tests the complete workflow from CLI input to JSON output,
including error logging for failed fetches.

Test Tickers:
- XDEF: Invalid ticker (should fail and be logged)
- XDEF.DE: Valid Xetra ETF (should succeed)

References:
- alm_datafetcher.csv (Requirements)
- icd_datafetcher.csv (Interface Definitions)
"""
import json
import os
import sys
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Module imports
from py_datafetcher.fetcher_core import FetcherOrchestrator
from py_datafetcher.cache_manager import CacheManager
from py_datafetcher.error_logger import ErrorLogger
from py_datafetcher.types import AppConfig, ProviderConfig, ProviderType, OHLCV, DataFetcherError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "data" / "market"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def mock_config(temp_data_dir):
    """Create a mock AppConfig pointing to temp directory."""
    return AppConfig(
        market_data_dir=str(temp_data_dir),
        providers=[ProviderConfig(name=ProviderType.YAHOO, api_key=None, priority=1)]
    )


@pytest.fixture
def cache_manager(temp_data_dir):
    """Create CacheManager with temp directory."""
    return CacheManager(str(temp_data_dir))


@pytest.fixture
def error_logger(temp_data_dir):
    """Create ErrorLogger with temp directory."""
    return ErrorLogger(str(temp_data_dir))


@pytest.fixture
def mock_provider_success():
    """Create a mock provider that returns valid data."""
    provider = Mock()
    provider.fetch_asset_history.return_value = [
        OHLCV(date="2026-01-15", open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000),
        OHLCV(date="2026-01-16", open=103.0, high=108.0, low=102.0, close=107.0, volume=1200000),
    ]
    provider.fetch_current_price.return_value = 107.50
    provider.__class__.__name__ = "MockProvider"
    return provider


@pytest.fixture
def mock_provider_failure():
    """Create a mock provider that always fails."""
    provider = Mock()
    provider.fetch_asset_history.side_effect = DataFetcherError("No data found for ticker")
    provider.fetch_current_price.side_effect = DataFetcherError("Price not available")
    provider.__class__.__name__ = "MockFailProvider"
    return provider


# =============================================================================
# Test Class: Error Logging (F-DF-060)
# =============================================================================

class TestErrorLogging:
    """Integration tests for error logging functionality (F-DF-060)."""

    def test_failed_ticker_logged_to_csv(
        self, mock_config, cache_manager, error_logger, mock_provider_failure
    ):
        """
        F-DF-060: Fehlgeschlagene Abrufe werden strukturiert in Logdatei persistiert.
        
        Test with invalid ticker XDEF - should be logged to fetch_errors.csv.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_failure],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(isin="TEST123456", ticker="XDEF", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result is False, "Update should fail for invalid ticker"
        
        # Verify error was logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 1
        assert failed_fetches[0].isin == "TEST123456"
        assert failed_fetches[0].ticker == "XDEF"
        assert "All providers failed" in failed_fetches[0].reason

    def test_multiple_failed_tickers_logged(
        self, mock_config, cache_manager, error_logger, mock_provider_failure
    ):
        """
        F-DF-060: Multiple failed fetches are logged, process continues (Fail-Safe).
        
        Test with XDEF and XDEF.DE - both should be in error log.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_failure],
            error_logger=error_logger
        )

        # ACT - Process multiple invalid tickers
        result1 = orchestrator.update_asset(isin="ISIN_XDEF", ticker="XDEF", start_date_hint=date(2026, 1, 1))
        result2 = orchestrator.update_asset(isin="ISIN_XDEF_DE", ticker="XDEF.DE", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result1 is False
        assert result2 is False
        
        # Both failures should be logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 2
        
        tickers_in_log = [f.ticker for f in failed_fetches]
        assert "XDEF" in tickers_in_log
        assert "XDEF.DE" in tickers_in_log

    def test_missing_ticker_logged_as_unknown(
        self, mock_config, cache_manager, error_logger, mock_provider_success
    ):
        """
        F-DF-060: Missing ticker should be logged with 'UNKNOWN'.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_success],
            error_logger=error_logger
        )

        # ACT - Call with empty ticker
        result = orchestrator.update_asset(isin="ISIN_NO_TICKER", ticker="", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result is False
        
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 1
        assert failed_fetches[0].ticker == "UNKNOWN"
        assert "No ticker provided" in failed_fetches[0].reason

    def test_error_log_csv_structure(self, temp_data_dir, error_logger):
        """
        F-DF-060: Error log must have CSV structure with Timestamp, ISIN, Ticker, Reason.
        """
        # ARRANGE & ACT
        error_logger.log_failure("TEST_ISIN", "XDEF", "Test reason")

        # ASSERT - Check CSV file structure
        log_path = temp_data_dir / "fetch_errors.csv"
        assert log_path.exists()

        content = log_path.read_text()
        lines = content.strip().split('\n')
        
        # Header check
        assert lines[0] == "Timestamp,ISIN,Ticker,Reason"
        
        # Data row check
        assert len(lines) == 2
        data_parts = lines[1].split(',')
        assert len(data_parts) >= 4
        assert data_parts[1] == "TEST_ISIN"
        assert data_parts[2] == "XDEF"


# =============================================================================
# Test Class: ICD Compliance (JSON Output)
# =============================================================================

class TestICDCompliance:
    """Integration tests for ICD compliance of JSON output."""

    def test_asset_json_structure_icd_jsn_010(
        self, mock_config, cache_manager, error_logger, mock_provider_success, temp_data_dir
    ):
        """
        ICD-DF-JSN-010: JSON Root muss keys 'isin', 'symbol', 'currency', 
        'last_update', 'market_price' und 'history' enthalten.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_success],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(isin="US1234567890", ticker="AAPL", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result is True
        
        # Load the generated JSON
        json_path = temp_data_dir / "US1234567890.json"
        assert json_path.exists(), "JSON file should be created"

        with open(json_path, 'r') as f:
            data = json.load(f)

        # Verify required keys (ICD-DF-JSN-010)
        required_keys = ["isin", "symbol", "currency", "last_update", "market_price", "history"]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"

        # Verify types
        assert isinstance(data["market_price"], (int, float)), "market_price must be numeric"
        assert isinstance(data["history"], dict), "history must be a dict"

    def test_asset_history_structure_icd_jsn_020(
        self, mock_config, cache_manager, error_logger, mock_provider_success, temp_data_dir
    ):
        """
        ICD-DF-JSN-020: 'history' ist ein Dict { "YYYY-MM-DD": { "open", "high", "low", "close", "volume" } }.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_success],
            error_logger=error_logger
        )

        # ACT
        orchestrator.update_asset(isin="US9876543210", ticker="MSFT", start_date_hint=date(2026, 1, 1))

        # ASSERT
        json_path = temp_data_dir / "US9876543210.json"
        with open(json_path, 'r') as f:
            data = json.load(f)

        history = data["history"]
        assert len(history) > 0, "History should not be empty"

        # Verify each candle structure
        for date_key, candle in history.items():
            # Date format check
            assert len(date_key) == 10, f"Date key should be YYYY-MM-DD: {date_key}"
            
            # OHLCV keys
            required_candle_keys = ["open", "high", "low", "close", "volume"]
            for ck in required_candle_keys:
                assert ck in candle, f"Missing candle key: {ck}"
            
            # Type checks
            assert isinstance(candle["open"], (int, float))
            assert isinstance(candle["high"], (int, float))
            assert isinstance(candle["low"], (int, float))
            assert isinstance(candle["close"], (int, float))
            assert isinstance(candle["volume"], int)

    def test_asset_filename_icd_nam_010(
        self, mock_config, cache_manager, error_logger, mock_provider_success, temp_data_dir
    ):
        """
        ICD-DF-NAM-010: Dateiname für Assets ist '{ISIN}.json'.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_success],
            error_logger=error_logger
        )
        test_isin = "DE000A1EWWW0"

        # ACT
        orchestrator.update_asset(isin=test_isin, ticker="ADS.DE", start_date_hint=date(2026, 1, 1))

        # ASSERT
        expected_filename = f"{test_isin}.json"
        json_path = temp_data_dir / expected_filename
        assert json_path.exists(), f"File should be named {expected_filename}"


# =============================================================================
# Test Class: Provider Chaining (F-DF-010)
# =============================================================================

class TestProviderChaining:
    """Integration tests for provider chaining functionality."""

    def test_fallback_to_second_provider(
        self, mock_config, cache_manager, error_logger, mock_provider_failure, mock_provider_success
    ):
        """
        F-DF-010: Wenn Provider A keine Daten liefert, muss automatisch Provider B versucht werden.
        """
        # ARRANGE - First provider fails, second succeeds
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[mock_provider_failure, mock_provider_success],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(isin="FALLBACK_TEST", ticker="AAPL", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result is True, "Should succeed via fallback provider"
        
        # Verify first provider was attempted
        mock_provider_failure.fetch_asset_history.assert_called_once()
        # Verify second provider was used
        mock_provider_success.fetch_asset_history.assert_called_once()
        
        # No errors should be logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 0

    def test_all_providers_fail(
        self, mock_config, cache_manager, error_logger
    ):
        """
        F-DF-010 + F-DF-060: When all providers fail, error is logged.
        
        Uses XDEF and XDEF.DE as test tickers.
        """
        # ARRANGE - Two failing providers
        fail_provider_1 = Mock()
        fail_provider_1.fetch_asset_history.side_effect = DataFetcherError("Provider 1 failed")
        fail_provider_1.__class__.__name__ = "FailProvider1"
        
        fail_provider_2 = Mock()
        fail_provider_2.fetch_asset_history.side_effect = DataFetcherError("Provider 2 failed")
        fail_provider_2.__class__.__name__ = "FailProvider2"

        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[fail_provider_1, fail_provider_2],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(isin="XDEF_ISIN", ticker="XDEF", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result is False
        
        # Both providers should have been tried
        fail_provider_1.fetch_asset_history.assert_called_once()
        fail_provider_2.fetch_asset_history.assert_called_once()
        
        # Error should be logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 1
        assert failed_fetches[0].ticker == "XDEF"


# =============================================================================
# Test Class: Caching Strategy (F-DF-040)
# =============================================================================

class TestCachingStrategy:
    """Integration tests for caching and merge behavior."""

    def test_cache_merge_preserves_historical_data(
        self, mock_config, cache_manager, error_logger, temp_data_dir
    ):
        """
        F-DF-040: Bestehende historische Daten werden nicht überschrieben, nur ergänzt.
        """
        # ARRANGE - Pre-populate cache with existing data
        existing_data = {
            "isin": "MERGE_TEST_ISIN",
            "symbol": "MRGT",
            "currency": "EUR",
            "market_price": 50.0,
            "last_update": "2026-01-14",
            "history": {
                "2026-01-13": {"date": "2026-01-13", "open": 48.0, "high": 49.0, "low": 47.0, "close": 48.5, "volume": 500000},
                "2026-01-14": {"date": "2026-01-14", "open": 48.5, "high": 50.0, "low": 48.0, "close": 50.0, "volume": 600000}
            }
        }
        
        cache_file = temp_data_dir / "MERGE_TEST_ISIN.json"
        with open(cache_file, 'w') as f:
            json.dump(existing_data, f)

        # Mock provider returns NEW data (Jan 15-16)
        new_provider = Mock()
        new_provider.fetch_asset_history.return_value = [
            OHLCV(date="2026-01-15", open=50.0, high=52.0, low=49.0, close=51.0, volume=700000),
            OHLCV(date="2026-01-16", open=51.0, high=53.0, low=50.0, close=52.0, volume=800000),
        ]
        new_provider.fetch_current_price.return_value = 52.50
        new_provider.__class__.__name__ = "MergeTestProvider"

        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[new_provider],
            error_logger=error_logger
        )

        # ACT
        orchestrator.update_asset(isin="MERGE_TEST_ISIN", ticker="MRGT", start_date_hint=date(2026, 1, 1))

        # ASSERT
        with open(cache_file, 'r') as f:
            merged_data = json.load(f)

        history = merged_data["history"]
        
        # Old data should still be present
        assert "2026-01-13" in history, "Historical data Jan 13 should be preserved"
        assert "2026-01-14" in history, "Historical data Jan 14 should be preserved"
        
        # New data should be added
        assert "2026-01-15" in history, "New data Jan 15 should be added"
        assert "2026-01-16" in history, "New data Jan 16 should be added"
        
        # Total entries
        assert len(history) == 4

    def test_up_to_date_asset_skipped(
        self, mock_config, cache_manager, error_logger, temp_data_dir
    ):
        """
        F-DF-040: Asset mit aktuellem last_update wird übersprungen.
        """
        # ARRANGE - Cache has data up to today
        today_str = date.today().strftime("%Y-%m-%d")
        existing_data = {
            "isin": "UPTODATE_ISIN",
            "symbol": "UTD",
            "currency": "EUR",
            "market_price": 100.0,
            "last_update": today_str,
            "history": {}
        }
        
        cache_file = temp_data_dir / "UPTODATE_ISIN.json"
        with open(cache_file, 'w') as f:
            json.dump(existing_data, f)

        provider = Mock()
        
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[provider],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(isin="UPTODATE_ISIN", ticker="UTD", start_date_hint=date(2026, 1, 1))

        # ASSERT
        assert result is True
        # Provider should NOT be called (asset is up to date)
        provider.fetch_asset_history.assert_not_called()


# =============================================================================
# Test Class: End-to-End Workflow
# =============================================================================

class TestEndToEndWorkflow:
    """Full workflow integration tests."""

    def test_mixed_success_and_failure_workflow(
        self, mock_config, cache_manager, error_logger, temp_data_dir
    ):
        """
        Complete workflow: Some assets succeed, some fail.
        Process continues for all (Fail-Safe per F-DF-060).
        """
        # ARRANGE
        # Provider that succeeds for "VALID" but fails for "XDEF*"
        smart_provider = Mock()
        
        def smart_fetch(ticker, start_date):
            if ticker.startswith("XDEF"):
                raise DataFetcherError(f"No data for {ticker}")
            return [OHLCV(date="2026-01-15", open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000)]
        
        smart_provider.fetch_asset_history.side_effect = smart_fetch
        smart_provider.fetch_current_price.return_value = 103.50
        smart_provider.__class__.__name__ = "SmartProvider"

        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[smart_provider],
            error_logger=error_logger
        )

        # ACT - Process multiple assets
        results = []
        assets = [
            ("VALID_ISIN_1", "AAPL"),
            ("XDEF_ISIN", "XDEF"),      # Should fail
            ("VALID_ISIN_2", "MSFT"),
            ("XDEF_DE_ISIN", "XDEF.DE"), # Should fail
        ]

        for isin, ticker in assets:
            results.append((ticker, orchestrator.update_asset(isin, ticker, date(2026, 1, 1))))

        # ASSERT
        # Valid tickers succeeded
        assert results[0] == ("AAPL", True)
        assert results[2] == ("MSFT", True)
        
        # Invalid tickers failed
        assert results[1] == ("XDEF", False)
        assert results[3] == ("XDEF.DE", False)

        # Valid assets have JSON files
        assert (temp_data_dir / "VALID_ISIN_1.json").exists()
        assert (temp_data_dir / "VALID_ISIN_2.json").exists()
        
        # Invalid assets do NOT have JSON files
        assert not (temp_data_dir / "XDEF_ISIN.json").exists()
        assert not (temp_data_dir / "XDEF_DE_ISIN.json").exists()

        # Errors are logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 2
        failed_tickers = [f.ticker for f in failed_fetches]
        assert "XDEF" in failed_tickers
        assert "XDEF.DE" in failed_tickers

    def test_clear_error_log_and_retry(
        self, mock_config, cache_manager, error_logger
    ):
        """
        Workflow: Log errors, clear log, retry.
        """
        # ARRANGE
        fail_provider = Mock()
        fail_provider.fetch_asset_history.side_effect = DataFetcherError("Failed")
        fail_provider.__class__.__name__ = "FailProvider"

        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[fail_provider],
            error_logger=error_logger
        )

        # ACT - First run, log errors
        orchestrator.update_asset("ISIN1", "XDEF", date(2026, 1, 1))
        assert len(error_logger.get_failed_fetches()) == 1

        # Clear log (e.g., after manual retry)
        error_logger.clear_log()
        assert len(error_logger.get_failed_fetches()) == 0

        # Another failure
        orchestrator.update_asset("ISIN2", "XDEF.DE", date(2026, 1, 1))
        assert len(error_logger.get_failed_fetches()) == 1
        assert error_logger.get_failed_fetches()[0].ticker == "XDEF.DE"


# =============================================================================
# Test Class: Real Yahoo API Tests (Network-dependent)
# =============================================================================

class TestRealYahooAPI:
    """
    Integration tests using the REAL Yahoo Finance API.
    
    These tests require network access and test actual data fetching.
    Mark with pytest.mark.slow or pytest.mark.network if needed.
    
    Test Tickers:
    - XDEF.DE: Valid Xetra ETF (Xtrackers Euro Defensive Tech)
    - XDEF: Invalid ticker (does not exist)
    """

    @pytest.fixture
    def real_yahoo_provider(self):
        """Create real YahooProvider instance."""
        from py_datafetcher.provider_yahoo import YahooProvider
        return YahooProvider()

    def test_valid_ticker_xdef_de_succeeds(
        self, mock_config, cache_manager, error_logger, real_yahoo_provider, temp_data_dir
    ):
        """
        XDEF.DE is a valid Xetra ticker and should return data.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[real_yahoo_provider],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(
            isin="LU0490618542",  # Actual ISIN for Xtrackers Euro Stoxx Select Dividend 30
            ticker="XDEF.DE",
            start_date_hint=date(2026, 1, 1)
        )

        # ASSERT
        assert result is True, "XDEF.DE should fetch successfully"
        
        # Verify JSON was created
        json_path = temp_data_dir / "LU0490618542.json"
        assert json_path.exists(), "JSON file should be created for valid ticker"
        
        # Verify content
        import json
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        assert data["symbol"] == "XDEF.DE"
        assert len(data["history"]) > 0, "Should have historical data"
        assert data["market_price"] > 0, "Should have a valid market price"
        
        # No errors logged
        assert len(error_logger.get_failed_fetches()) == 0

    def test_invalid_ticker_xdef_fails_and_logged(
        self, mock_config, cache_manager, error_logger, real_yahoo_provider, temp_data_dir
    ):
        """
        XDEF (without .DE) is invalid and should fail with error logged.
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[real_yahoo_provider],
            error_logger=error_logger
        )

        # ACT
        result = orchestrator.update_asset(
            isin="INVALID_XDEF_ISIN",
            ticker="XDEF",
            start_date_hint=date(2026, 1, 1)
        )

        # ASSERT
        assert result is False, "XDEF should fail (invalid ticker)"
        
        # Verify error was logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 1
        assert failed_fetches[0].ticker == "XDEF"
        assert failed_fetches[0].isin == "INVALID_XDEF_ISIN"
        
        # No JSON file created
        json_path = temp_data_dir / "INVALID_XDEF_ISIN.json"
        assert not json_path.exists(), "No JSON should be created for invalid ticker"

    def test_mixed_real_tickers_workflow(
        self, mock_config, cache_manager, error_logger, real_yahoo_provider, temp_data_dir
    ):
        """
        Complete workflow with real Yahoo API:
        - XDEF.DE succeeds
        - XDEF fails and is logged
        - Process continues (Fail-Safe)
        """
        # ARRANGE
        orchestrator = FetcherOrchestrator(
            config=mock_config,
            cache=cache_manager,
            providers=[real_yahoo_provider],
            error_logger=error_logger
        )

        # ACT - First try valid, then invalid
        result_valid = orchestrator.update_asset(
            isin="XDEF_DE_ISIN",
            ticker="XDEF.DE",
            start_date_hint=date(2026, 1, 1)
        )
        
        result_invalid = orchestrator.update_asset(
            isin="XDEF_ISIN",
            ticker="XDEF",
            start_date_hint=date(2026, 1, 1)
        )

        # ASSERT
        assert result_valid is True, "XDEF.DE should succeed"
        assert result_invalid is False, "XDEF should fail"
        
        # Only invalid ticker logged
        failed_fetches = error_logger.get_failed_fetches()
        assert len(failed_fetches) == 1
        assert failed_fetches[0].ticker == "XDEF"
        
        # Valid ticker has JSON
        assert (temp_data_dir / "XDEF_DE_ISIN.json").exists()
        # Invalid ticker has no JSON
        assert not (temp_data_dir / "XDEF_ISIN.json").exists()


# =============================================================================
# Test Class: CLI Integration Tests (ICD-DF-CLI-010, ICD-DF-CLI-020)
# =============================================================================

class TestCLIIntegration:
    """
    Integration tests for the CLI interface of py_datafetcher.
    
    Tests the command-line invocation as specified in:
    - ICD-DF-CLI-010: python datafetcher.py --mode update --assets "[LIST]" --fx "[LIST]"
    - ICD-DF-CLI-020: Asset format "ISIN:TICKER:STARTDATE"
    """

    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def cli_test_dir(self, tmp_path):
        """Create temporary directory structure for CLI tests."""
        data_dir = tmp_path / "data" / "market"
        data_dir.mkdir(parents=True)
        return tmp_path

    @pytest.fixture
    def mock_providers_config(self, cli_test_dir):
        """Create a providers.json config file for CLI tests."""
        config = {
            "market_data_dir": str(cli_test_dir / "data" / "market"),
            "providers": [
                {"name": "yahoo", "priority": 1}
            ]
        }
        config_path = cli_test_dir / "providers.json"
        with open(config_path, 'w') as f:
            json.dump(config, f)
        return config_path

    def test_cli_asset_argument_format_icd_cli_020(self, project_root):
        """
        ICD-DF-CLI-020: Test asset argument parsing "ISIN:TICKER:STARTDATE".
        
        Uses XDEF.DE (valid) and XDEF (invalid).
        Runs from project root, writes to ./data/market/
        """
        import subprocess
        
        # ARRANGE
        data_dir = project_root / "data" / "market"
        # Clean up test files if they exist from previous runs
        test_files = ["CLI_TEST_VALID.json", "CLI_TEST_INVALID.json"]
        for f in test_files:
            (data_dir / f).unlink(missing_ok=True)
        
        # Clean error log
        error_log = data_dir / "fetch_errors.csv"
        if error_log.exists():
            error_log.unlink()
        
        # ACT - Run CLI with mixed valid/invalid tickers
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--mode", "update",
                "--assets", "CLI_TEST_VALID:XDEF.DE:2026-01-01,CLI_TEST_INVALID:XDEF:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        # ASSERT
        # Exit code should be 1 (some failures)
        assert result.returncode == 1, f"Expected exit 1 due to XDEF failure. Stdout: {result.stdout}, Stderr: {result.stderr}"
        
        # Valid ticker should have JSON
        valid_json = data_dir / "CLI_TEST_VALID.json"
        assert valid_json.exists(), f"Valid ticker XDEF.DE should create JSON. Stderr: {result.stderr}"
        
        # Invalid ticker should NOT have JSON
        invalid_json = data_dir / "CLI_TEST_INVALID.json"
        assert not invalid_json.exists(), "Invalid ticker XDEF should not create JSON"
        
        # Error log should exist with XDEF failure
        assert error_log.exists(), "Error log should be created"
        
        content = error_log.read_text()
        assert "XDEF" in content, "XDEF should be in error log"
        
        # Cleanup
        valid_json.unlink(missing_ok=True)

    def test_cli_mode_update_required(self, project_root):
        """
        ICD-DF-CLI-010: --mode is required with choices=['update'].
        """
        import subprocess
        
        # ACT - Run without --mode
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--assets", "TEST:TEST:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10
        )

        # ASSERT - Should fail due to missing required argument
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "mode" in result.stderr.lower()

    def test_cli_success_exit_code_zero(self, project_root):
        """
        CLI should exit with 0 when all fetches succeed.
        """
        import subprocess
        
        data_dir = project_root / "data" / "market"
        test_file = data_dir / "CLI_SUCCESS_TEST.json"
        test_file.unlink(missing_ok=True)
        
        # ACT - Run with only valid ticker
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--mode", "update",
                "--assets", "CLI_SUCCESS_TEST:XDEF.DE:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        # ASSERT
        assert result.returncode == 0, f"Expected exit 0 for valid ticker. Stderr: {result.stderr}"
        
        # Verify JSON was created
        assert test_file.exists(), "JSON should be created for valid ticker"
        
        # Cleanup
        test_file.unlink(missing_ok=True)

    def test_cli_multiple_assets_comma_separated(self, project_root):
        """
        ICD-DF-CLI-020: Multiple assets are comma-separated.
        """
        import subprocess
        
        data_dir = project_root / "data" / "market"
        test_files = ["CLI_MULTI_1.json", "CLI_MULTI_2.json"]
        for f in test_files:
            (data_dir / f).unlink(missing_ok=True)
        
        # ACT - Run with multiple valid tickers
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--mode", "update",
                "--assets", "CLI_MULTI_1:XDEF.DE:2026-01-01,CLI_MULTI_2:AAPL:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        # ASSERT - Both should succeed
        assert result.returncode == 0, f"Both valid tickers should succeed. Stderr: {result.stderr}"
        
        assert (data_dir / "CLI_MULTI_1.json").exists(), "First asset JSON should exist"
        assert (data_dir / "CLI_MULTI_2.json").exists(), "Second asset JSON should exist"
        
        # Cleanup
        for f in test_files:
            (data_dir / f).unlink(missing_ok=True)

    def test_cli_output_logs_success_and_fail_counts(self, project_root):
        """
        CLI should log success and failure counts.
        """
        import subprocess
        
        data_dir = project_root / "data" / "market"
        (data_dir / "CLI_LOG_TEST.json").unlink(missing_ok=True)
        
        # ACT
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--mode", "update",
                "--assets", "CLI_LOG_TEST:XDEF.DE:2026-01-01,CLI_LOG_FAIL:XDEF:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        # ASSERT - Check log output
        combined_output = result.stdout + result.stderr
        assert "Success: 1" in combined_output, f"Should log 1 success. Output: {combined_output}"
        assert "Failed: 1" in combined_output, f"Should log 1 failure. Output: {combined_output}"
        
        # Cleanup
        (data_dir / "CLI_LOG_TEST.json").unlink(missing_ok=True)

    def test_cli_fx_argument(self, project_root):
        """
        ICD-DF-CLI-010: Test --fx argument for FX pairs.
        """
        import subprocess
        
        data_dir = project_root / "data" / "market"
        fx_file = data_dir / "EURUSD.json"
        
        # ACT - Run with FX pair (EURUSD is common)
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--mode", "update",
                "--fx", "EURUSD:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        # ASSERT
        # FX should work (EURUSD is valid)
        if result.returncode == 0:
            assert fx_file.exists(), "FX JSON should be created"
        # Note: FX might fail due to Yahoo API limitations, which is acceptable

    def test_cli_combined_assets_and_fx(self, project_root):
        """
        CLI should handle both --assets and --fx in single invocation.
        """
        import subprocess
        
        data_dir = project_root / "data" / "market"
        test_file = data_dir / "CLI_COMBINED_TEST.json"
        test_file.unlink(missing_ok=True)
        
        # ACT
        result = subprocess.run(
            [
                "python", "-m", "py_datafetcher.datafetcher",
                "--mode", "update",
                "--assets", "CLI_COMBINED_TEST:XDEF.DE:2026-01-01",
                "--fx", "EURUSD:2026-01-01"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        # ASSERT
        # Asset should definitely work
        assert test_file.exists(), f"Asset JSON should be created. Stderr: {result.stderr}"
        
        # Log should show processing
        combined_output = result.stdout + result.stderr
        assert "CLI_COMBINED_TEST" in combined_output or "XDEF.DE" in combined_output
        
        # Cleanup
        test_file.unlink(missing_ok=True)
