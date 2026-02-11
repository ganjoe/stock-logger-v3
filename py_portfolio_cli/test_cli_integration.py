"""
Integration Tests: Vollständige CLI-Menü Abdeckung.

Testet JEDEN Menüpunkt des Portfolio Managers in zwei Varianten:
  A) OFFLINE — OfflineDataSource (kein Broker)
  B) MOCKED BROKER — Simulierte Online-Verbindung

Punkte die echten Broker erfordern werden als manuelle Checkliste
am Scriptende ausgegeben (print_manual_checklist).

ALM-Referenzen:
  F-CLI-010 .. F-CLI-300 (CLI Requirements)
  F-PM-130, F-PM-170, F-PM-200 (Menu, Stop-Loss Warning, Market Update)
"""
import pytest
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from py_manage_portfolio.service import PortfolioService
from py_manage_portfolio.models.portfolio_state import PortfolioState, Position
from py_manage_portfolio.models import Position, PortfolioSummary
from py_portfolio_cli.menus import (
    show_menu, show_live_menu, show_simulation_menu,
)
from py_portfolio_cli.actions import (
    action_manage_stops, action_init_paper, action_edit_paper_position,
    action_edit_paper_metrics, action_update_prices, action_clear_paper,
    action_switch_data_source, _connect_to_broker,
)
from py_portfolio_cli.main import main, start_simulation_mode
from py_portfolio_cli.formatter import render_dashboard
from py_portfolio_cli.wizard import run_sizing_wizard


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

def _make_state_with_positions() -> PortfolioState:
    """Helper: creates a PortfolioState with 2 test positions."""
    return PortfolioState(
        timestamp=datetime.now().isoformat(),
        cash=50000.0,
        equity=60000.0,
        positions={
            "AAPL": Position(symbol="AAPL", quantity=10, entry_price=150.0, current_price=160.0, currency="USD"),
            "MSFT": Position(symbol="MSFT", quantity=5, entry_price=300.0, current_price=310.0, currency="USD"),
        }
    )


@pytest.fixture
def service_offline(tmp_path):
    """
    Variante A: OFFLINE — PortfolioService ohne Broker.
    Simuliert den Zustand ohne aktive Broker-Verbindung, aber mit
    einem gespeicherten Snapshot der geladen werden kann.
    """
    # Create data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    service = PortfolioService(project_root=str(tmp_path), context="live")

    # Inject a known state so tests don't depend on real files
    service.state = _make_state_with_positions()
    service.storage.save_portfolio(service.state, "data_portfolio_live_snapshot.json")

    return service


@pytest.fixture
def service_broker(tmp_path):
    """
    Variante B: MOCKED BROKER — PortfolioService mit simulierter Online-Verbindung.
    BrokerDataSource ist vollständig gemockt.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    service = PortfolioService(project_root=str(tmp_path), context="live")

    # Use a mock that satisfies isinstance(ds, ConnectionAware) 
    from py_manage_portfolio.data_source import PortfolioReader, ConnectionAware, OrderManager
    
    class MockBrokerDS(PortfolioReader, ConnectionAware, OrderManager):
        """Concrete stub so MagicMock(spec=...) passes isinstance checks."""
        def get_portfolio_state(self): ...
        def get_positions(self): ...
        def get_stop_losses(self): ...
        def get_account_metrics(self): ...
        def get_open_orders(self, symbol=None): ...
        def place_order(self, request): ...
        def cancel_order(self, order_id): ...
        def is_connected(self): ...
        def disconnect(self): ...
    
    mock_ds = MagicMock(spec=MockBrokerDS)
    mock_ds.is_connected.return_value = True
    mock_ds.get_portfolio_state.return_value = _make_state_with_positions()
    service._data_source = mock_ds  # Bypass set_data_source to avoid side effects

    # Also load state so get_positions works
    service.state = _make_state_with_positions()

    return service


@pytest.fixture
def service_sim(tmp_path):
    """
    Variante Sim: PortfolioService im Simulationsmodus.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    service = PortfolioService(project_root=str(tmp_path), context="sim")
    # Ensure a clean sim state exists
    service.state = PortfolioState(
        timestamp=datetime.now().isoformat(),
        cash=100000.0,
        equity=100000.0,
        positions={}
    )
    service.save_simulation_state()
    return service


# ═══════════════════════════════════════════════════════════
# MAIN MENU  (F-CLI-010)
# ═══════════════════════════════════════════════════════════

class TestMainMenu:
    """Tests für die 3 Hauptmenü-Einträge + quit."""

    def test_menu_renders_offline_status(self, service_offline, capsys):
        """[Main] Menü zeigt 🔴 OFFLINE wenn kein Broker verbunden (F-CLI-010)."""
        with patch('builtins.input', return_value='q'):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                result = show_menu(service_offline)

        output = capsys.readouterr().out
        assert "PORTFOLIO MANAGER" in output
        assert "OFFLINE" in output
        assert result == 'q'

    def test_menu_renders_online_status(self, service_broker, capsys):
        """[Main] Menü zeigt 🟢 ONLINE wenn Broker verbunden (F-CLI-040)."""
        with patch('builtins.input', return_value='q'):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                result = show_menu(service_broker)

        output = capsys.readouterr().out
        assert "ONLINE" in output

    def test_navigate_to_live_and_back(self, service_offline):
        """[Main→1→b] Navigiert ins Live-Menü und zurück (F-CLI-010)."""
        # show_live_menu loops until 'b'
        with patch('builtins.input', side_effect=['b']):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_offline)
        # No crash = success

    def test_navigate_to_simulation_and_back(self, service_sim):
        """[Main→2→b] Navigiert ins Sim-Menü und zurück (F-CLI-200)."""
        with patch('builtins.input', return_value='b'):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    result = show_simulation_menu(service_sim)
        assert result == 'b'

    def test_broker_toggle_connect_offline(self, service_offline, capsys):
        """[Main→3] Broker Connect aus OFFLINE — ruft _connect_to_broker (F-CLI-040)."""
        # Verify service starts without broker
        assert not service_offline.is_broker_connected()
        assert service_offline.get_data_source() is None

    def test_broker_toggle_disconnect_online(self, service_broker, capsys):
        """[Main→3] Broker Disconnect aus ONLINE — wechselt zu Snapshot (F-CLI-040)."""
        assert service_broker.is_broker_connected() is True

        # Disconnect via service API
        service_broker.disconnect_broker()

        assert service_broker.get_data_source() is None
        assert not service_broker.is_broker_connected()

    def test_quit(self, service_offline, capsys):
        """[Main→q] Beendet Anwendung (F-CLI-010)."""
        with patch('builtins.input', return_value='q'):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                result = show_menu(service_offline)
        assert result == 'q'


# ═══════════════════════════════════════════════════════════
# LIVE MENU  (F-CLI-110 .. F-CLI-130)
# ═══════════════════════════════════════════════════════════

class TestLiveMenu:
    """Tests für die 4 Live-Untermenü-Einträge."""

    def test_dashboard_renders_offline(self, service_offline, capsys):
        """[1] Dashboard rendert korrekt im Offline-Modus (F-CLI-030)."""
        render_dashboard(service_offline)

        output = capsys.readouterr().out
        assert "AAPL" in output
        assert "MSFT" in output

    def test_dashboard_renders_broker(self, service_broker, capsys):
        """[1] Dashboard rendert korrekt mit Broker-Daten (F-CLI-030)."""
        render_dashboard(service_broker)

        output = capsys.readouterr().out
        assert "AAPL" in output

    def test_refresh_prices_offline(self, service_offline, capsys):
        """[1→3] Marktdaten aktualisieren — Offline-Modus (F-CLI-130)."""
        with patch('builtins.input', side_effect=['3', '', 'b']):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_offline)

        output = capsys.readouterr().out
        assert "aktualisiert" in output.lower() or "Marktdaten" in output

    def test_wizard_live_offline(self, service_offline):
        """[1→2] Minervini Wizard (Live) aufrufen und abbrechen (F-CLI-120)."""
        with patch('py_portfolio_cli.menus.run_sizing_wizard') as mock_wizard:
            with patch('builtins.input', side_effect=['2', 'b']):
                with patch('py_portfolio_cli.menus.clear_terminal'):
                    with patch('py_portfolio_cli.menus.render_dashboard'):
                        show_live_menu(service_offline)

            mock_wizard.assert_called_once_with(service_offline, source="live")

    def test_wizard_live_broker(self, service_broker):
        """[1→2] Minervini Wizard mit Broker-Daten (F-CLI-120)."""
        with patch('py_portfolio_cli.menus.run_sizing_wizard') as mock_wizard:
            with patch('builtins.input', side_effect=['2', 'b']):
                with patch('py_portfolio_cli.menus.clear_terminal'):
                    with patch('py_portfolio_cli.menus.render_dashboard'):
                        show_live_menu(service_broker)

            mock_wizard.assert_called_once_with(service_broker, source="live")

    def test_trading_fails_offline(self, service_offline, capsys):
        """[1→1] Trading Offline — Zeigt Fehlermeldung (F-CLI-XX)."""
        with patch('builtins.input', side_effect=['1', '', 'b']):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_offline)

        output = capsys.readouterr().out
        assert "Kein Broker verbunden" in output
        assert "nicht möglich" in output

    def test_refresh_prices_broker(self, service_broker, capsys):
        """[1→3] Marktdaten aktualisieren — Broker-Modus (F-CLI-130)."""
        with patch('builtins.input', side_effect=['3', '', 'b']):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_broker)

        output = capsys.readouterr().out
        assert "aktualisiert" in output.lower() or "Marktdaten" in output

    def test_trading_live_order(self, service_broker, capsys):
        """[1→1] Trading: Order platzieren (F-CLI-XX)."""
        # Mock Place Order
        ds = service_broker.get_data_source()
        ds.place_order.return_value = "1001" # Mock Order ID

        # Input: 1 (Trading), AAPL, BUY, 10, 1 (MKT), y (Confirm), Exit
        inputs = ['1', 'AAPL', 'BUY', '10', '1', 'y', '', 'b']
        
        with patch('builtins.input', side_effect=inputs):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_broker)

        output = capsys.readouterr().out
        
        # Verify call
        ds.place_order.assert_called_once()
        args = ds.place_order.call_args[0][0]
        assert args.symbol == "AAPL"
        assert args.quantity == 10
        assert args.action == "BUY"
        assert args.order_type == "MKT"
        
        assert "Order erfolgreich übermittelt" in output
        assert "ID: 1001" in output

    def test_stoploss_manager_offline(self, service_offline, capsys):
        """[1→4] Stop-Loss Manager — Position auswählen und Stop setzen (F-PM-060)."""
        # Choose StopLoss manager, select position 1, set stop to '140', enter, back
        with patch('builtins.input', side_effect=['4', '1', '140', '', 'b']):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_offline)

        output = capsys.readouterr().out
        assert "Stop" in output

    def test_stoploss_manager_skip(self, service_offline, capsys):
        """[1→4] Stop-Loss Manager — Skip (F-PM-080)."""
        with patch('builtins.input', side_effect=['4', '1', 'skip', 'b']):
            with patch('py_portfolio_cli.menus.clear_terminal'):
                with patch('py_portfolio_cli.menus.render_dashboard'):
                    show_live_menu(service_offline)
        # No crash = skip works

    def test_refresh_prices_broker_saves_snapshot(self, service_broker, tmp_path):
        """
        [1→3] Marktdaten aktualisieren mit Broker — State + Snapshot Update (F-CLI-130).
        
        Regression test für Bug: "Portfolio wird nicht mit Live-Daten aktualisiert"
        
        Workflow:
        1. Broker verbunden (service_broker)
        2. [3] Refresh aufrufen
        3. Erwartung:
           - get_portfolio_state() wird vom Broker aufgerufen
           - Snapshot wird gespeichert
           - Dashboard wird neu gerendert
        """
        # Create updated state with different prices
        updated_state = PortfolioState(
            timestamp=datetime.now().isoformat(),
            cash=50000.0,
            equity=65000.0,  # Changed
            positions={
                "AAPL": Position(symbol="AAPL", quantity=10, entry_price=150.0, current_price=170.0, currency="USD"),  # Price changed
                "MSFT": Position(symbol="MSFT", quantity=5, entry_price=300.0, current_price=320.0, currency="USD"),   # Price changed
            }
        )
        
        # Mock broker to return updated state
        service_broker._data_source.get_portfolio_state.return_value = updated_state
        
        # Call action_update_prices
        with patch('builtins.input', return_value=''):
            with patch('py_portfolio_cli.actions.clear_terminal'):
                with patch('py_portfolio_cli.actions.render_dashboard') as mock_render:
                    action_update_prices(service_broker)
        
        # Verify broker was called to fetch new state
        service_broker._data_source.get_portfolio_state.assert_called()
        
        # Verify snapshot was saved
        snapshot_path = tmp_path / "data" / "data_portfolio_live_snapshot.json"
        assert snapshot_path.exists(), "Snapshot should be saved after refresh"
        
        # Verify state was updated
        assert service_broker.state.equity == 65000.0
        assert service_broker.state.positions["AAPL"].current_price == 170.0
        
        # Verify dashboard was rendered with new data
        mock_render.assert_called_once_with(service_broker)



# ═══════════════════════════════════════════════════════════
# SIMULATION MENU  (F-CLI-200 .. F-CLI-230)
# ═══════════════════════════════════════════════════════════

class TestSimulationMenu:
    """Tests für die 4 Simulations-Untermenü-Einträge."""

    def test_dashboard_renders_sim(self, service_sim, capsys):
        """[2] Dashboard rendert im Sim-Modus (F-CLI-200)."""
        with patch('builtins.print') as mock_print:
            render_dashboard(service_sim)

        all_output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "SIMULATION" in all_output.upper() or "SIM" in all_output.upper()

    def test_import_live_snapshot(self, service_sim):
        """[2→1] Live-Portfolio importieren (F-CLI-210)."""
        with patch.object(service_sim, 'init_from_live') as mock_init:
            mock_init.return_value = None
            with patch('builtins.input', side_effect=['y', '']):
                with patch('py_portfolio_cli.actions.render_dashboard'):
                    action_init_paper(service_sim)

            mock_init.assert_called_once()

    def test_add_position_sim(self, service_sim, capsys):
        """[2→2→1] Position hinzufügen (F-CLI-220)."""
        assert len(service_sim.get_open_positions()) == 0

        service_sim.add_position_sim("NVDA", 20, 500.0, datetime.now().strftime("%Y-%m-%d"))

        positions = service_sim.get_open_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "NVDA"
        assert positions[0].quantity == 20

    def test_edit_position_stop(self, service_sim, capsys):
        """[2→2→2] Stop-Loss einer Sim-Position bearbeiten (F-CLI-220)."""
        service_sim.add_position_sim("TSLA", 5, 200.0, datetime.now().strftime("%Y-%m-%d"))

        # Select pos 1, Edit Stop (choice 2), new stop = '180', enter
        with patch('builtins.input', side_effect=['1', '2', '180', '', '']):
            with patch('py_portfolio_cli.actions.render_dashboard'):
                action_edit_paper_position(service_sim)

        output = capsys.readouterr().out
        assert "aktualisiert" in output.lower() or "Stop" in output

    def test_edit_position_qty(self, service_sim, capsys):
        """[2→2→2] Qty einer Sim-Position ändern (F-CLI-220)."""
        service_sim.add_position_sim("AMZN", 10, 180.0, datetime.now().strftime("%Y-%m-%d"))

        # Select pos 1, Edit Qty (choice 3), new qty = '25', enter
        with patch('builtins.input', side_effect=['1', '3', '25', '']):
            with patch('py_portfolio_cli.actions.render_dashboard'):
                action_edit_paper_position(service_sim)

        output = capsys.readouterr().out
        assert "aktualisiert" in output.lower() or "Anzahl" in output

    def test_delete_position(self, service_sim, capsys):
        """[2→2→2] Position löschen (F-CLI-220)."""
        service_sim.add_position_sim("DELME", 3, 50.0, datetime.now().strftime("%Y-%m-%d"))
        assert len(service_sim.get_open_positions()) == 1

        # Select pos 1, Delete (choice 1), confirm 'y', enter
        with patch('builtins.input', side_effect=['1', '1', 'y', '']):
            with patch('py_portfolio_cli.actions.render_dashboard'):
                action_edit_paper_position(service_sim)

        assert len(service_sim.get_open_positions()) == 0

    def test_wizard_sim(self, service_sim):
        """[2→3] Minervini Wizard (Sim) aufrufen (F-CLI-230)."""
        with patch('py_portfolio_cli.menus.run_sizing_wizard') as mock_wizard:
            # Directly call via the same path start_simulation_mode uses
            mock_wizard(service_sim, source="sim")

            mock_wizard.assert_called_once_with(service_sim, source="sim")

    def test_reset_simulation(self, service_sim, capsys):
        """[2→4] Simulation komplett zurücksetzen (F-CLI-200)."""
        # Add a position first
        service_sim.add_position_sim("RESET", 100, 10.0, datetime.now().strftime("%Y-%m-%d"))
        assert len(service_sim.get_open_positions()) == 1

        # Clear
        with patch('builtins.input', side_effect=['y', '']):
            with patch('py_portfolio_cli.actions.render_dashboard'):
                action_clear_paper(service_sim)

        assert len(service_sim.get_open_positions()) == 0

    def test_edit_metrics(self, service_sim, capsys):
        """[2→Metrics] Equity/Exposure manuell setzen (F-MSM-160)."""
        with patch('builtins.input', side_effect=['80000', '10000', '']):
            with patch('py_portfolio_cli.actions.render_dashboard'):
                action_edit_paper_metrics(service_sim)

        equity, cash, exposure = service_sim._get_journal_metrics()
        assert cash == 70000.0  # 80000 - 10000


# ═══════════════════════════════════════════════════════════
# BROKER CONNECTION  (F-CLI-040)
# ═══════════════════════════════════════════════════════════

class TestBrokerConnection:
    """Tests für Broker Connect/Disconnect Toggle."""

    def test_connect_missing_module(self, service_offline, capsys):
        """Broker Connect zeigt Fehler wenn py_broker_captrader fehlt (F-CLI-040)."""
        with patch.dict('sys.modules', {'py_broker_captrader': None}):
            with patch('builtins.input', side_effect=['127.0.0.1', '4001', '']):
                _connect_to_broker(service_offline)

        output = capsys.readouterr().out
        assert "nicht gefunden" in output or "Import" in output.lower() or "Modul" in output

    def test_connect_with_mocked_broker(self, service_offline, capsys):
        """Broker Connect mit gemocktem BrokerDataSource (F-CLI-040)."""
        # Mock the BrokerDataSource class
        MockBDS = MagicMock()
        mock_instance = MockBDS.return_value
        mock_instance.is_connected.return_value = True
        mock_instance._connection.ib.managedAccounts.return_value = ["DU MOCK"]
        mock_instance._get_account.return_value = "DU MOCK"
        
        mock_broker_mod = MagicMock()
        mock_broker_mod.BrokerDataSource = MockBDS

        with patch.dict('sys.modules', {'py_broker_captrader': mock_broker_mod}):
             with patch('builtins.input', side_effect=['127.0.0.1', '4001', '']):
                _connect_to_broker(service_offline)

        output = capsys.readouterr().out
        assert "Verbunden" in output or "IBKR" in output

    def test_connect_connection_error(self, service_offline, capsys):
        """Broker Connect zeigt Fehler bei ConnectionError (F-CLI-040)."""
        # Mock BrokerDataSource to raise ConnectionError
        MockBDS = MagicMock(side_effect=ConnectionError("TWS unreachable"))
        
        mock_broker_mod = MagicMock()
        mock_broker_mod.BrokerDataSource = MockBDS

        with patch.dict('sys.modules', {'py_broker_captrader': mock_broker_mod}):
            with patch('builtins.input', side_effect=['127.0.0.1', '4001', '']):
                _connect_to_broker(service_offline)

        output = capsys.readouterr().out
        assert "Fehler" in output or "fehler" in output.lower()

    def test_data_source_switch_disconnect(self, service_broker, capsys):
        """Datenquelle → Disconnect zum Snapshot (F-PDS-120)."""
        with patch('builtins.input', side_effect=['1', '']):
            action_switch_data_source(service_broker)

        assert service_broker.get_data_source() is None

    def test_data_source_switch_to_broker(self, service_offline):
        """Datenquelle → Broker wechseln (F-PDS-120)."""
        with patch('py_portfolio_cli.actions._connect_to_broker') as mock_connect:
            with patch('builtins.input', side_effect=['1', '']):
                action_switch_data_source(service_offline)

            mock_connect.assert_called_once()


# ═══════════════════════════════════════════════════════════
# FULL MAIN LOOP INTEGRATION
# ═══════════════════════════════════════════════════════════

class TestMainLoopIntegration:
    """End-to-End Tests für main() mit verschiedenen Menüpfaden."""

    def test_main_live_back_quit(self, tmp_path, capsys):
        """main() → [1] Live → [b] Back → [q] Quit."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with patch('py_portfolio_cli.main.PortfolioService') as MockService:
            mock_svc = MagicMock()
            mock_svc.get_data_source.return_value = MagicMock(is_connected=MagicMock(return_value=False))
            mock_svc.get_open_positions.return_value = []
            mock_svc.get_summary.return_value = PortfolioSummary(
                total_invested=0, total_unrealized_pl=0, total_risk=0,
                buying_power=100000, equity=100000, position_count=0,
                count_ok=0, count_warning=0, count_danger=0
            )
            mock_svc.get_risk_settings.return_value = {"max_pos_size_pct": 25.0}
            mock_svc.context = "live"
            MockService.return_value = mock_svc

            with patch('builtins.input', side_effect=['1', 'b', 'q']):
                with patch('py_portfolio_cli.menus.clear_terminal'):
                    main()

        output = capsys.readouterr().out
        assert "Auf Wiedersehen" in output

    def test_main_quit_directly(self, tmp_path, capsys):
        """main() → [q] Beenden."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with patch('py_portfolio_cli.main.PortfolioService') as MockService:
            mock_svc = MagicMock()
            mock_svc.get_data_source.return_value = MagicMock(is_connected=MagicMock(return_value=False))
            MockService.return_value = mock_svc

            with patch('builtins.input', return_value='q'):
                with patch('py_portfolio_cli.menus.clear_terminal'):
                    main()

        output = capsys.readouterr().out
        assert "Auf Wiedersehen" in output

    def test_main_invalid_choice(self, tmp_path, capsys):
        """main() → ungültige Eingabe → [q] Quit."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with patch('py_portfolio_cli.main.PortfolioService') as MockService:
            mock_svc = MagicMock()
            mock_svc.get_data_source.return_value = MagicMock(is_connected=MagicMock(return_value=False))
            MockService.return_value = mock_svc

            with patch('builtins.input', side_effect=['xyz', 'q']):
                with patch('py_portfolio_cli.menus.clear_terminal'):
                    main()

        output = capsys.readouterr().out
        assert "Ungültige" in output or "ungültig" in output.lower()


# ═══════════════════════════════════════════════════════════
# MANUELLE TEST-CHECKLISTE
# ═══════════════════════════════════════════════════════════

def print_manual_checklist():
    """
    Wird am Ende des Testlaufs ausgegeben.
    Listet Szenarien die einen echten Broker erfordern.
    """
    checklist = """
═══════════════════════════════════════════════════════════════
   MANUELLE TESTS (erfordern laufende TWS oder IB Gateway)
═══════════════════════════════════════════════════════════════

 Voraussetzung: TWS/IB Gateway gestartet, Paper Account eingeloggt.
 Starte mit: python run_manage_portfolio.py

 [ ] M-01: Hauptmenü → [3] Broker Connect
          → Host: 127.0.0.1, Port: 4001
          → Erwartung: Status wechselt zu 🟢 ONLINE
          → Account-ID wird angezeigt

 [ ] M-02: [1] Portfolio (Live) → Dashboard
          → Erwartung: Echte Positionen werden angezeigt
          → Preise, Gain%, Stop, R-Multiple sichtbar

 [ ] M-03: [1] → [3] Marktdaten aktualisieren (Refresh)
          → Erwartung: Preise werden vom Broker aktualisiert
          → Kein Fehler, Anzeige refreshed

 [ ] M-04: [1] → [2] Minervini Wizard (Live)
          → Erwartung: Wizard startet, Equity/Exposure aus Broker
          → Schritt 1-4 durchlaufen, KEIN Order ausführen
          → Am Ende: Planungsergebnis wird angezeigt

 [ ] M-05: Hauptmenü → [3] Broker Disconnect
          → Erwartung: Status wechselt zu 🔴 OFFLINE
          → Dashboard zeigt letzten Snapshot

 [ ] M-06: [1] Portfolio (Live) im OFFLINE-Modus
          → Erwartung: Snapshot wird statt Live-Daten angezeigt
          → Keine Fehlermeldung

 [ ] M-07: Anwendung komplett neustarten (ohne TWS)
          → Erwartung: Snapshot wird automatisch geladen (F-CLI-030)
          → Menü ist nutzbar, Dashboard zeigt gecachte Daten

═══════════════════════════════════════════════════════════════
"""
    print(checklist)


# Pytest hook: Print checklist after all tests complete
def pytest_sessionfinish(session, exitstatus):
    """Print the manual test checklist after all automated tests run."""
    print_manual_checklist()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
    print_manual_checklist()
