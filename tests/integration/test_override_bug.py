import pytest
import os
from py_manage_portfolio.service import PortfolioService

class TestOverrideBug:
    @pytest.fixture
    def setup_project(self, tmp_path):
        """Creates a temporary project structure."""
        project_root = tmp_path
        
        # Risk Settings
        settings_path = project_root / "data_risksettings.csv"
        settings_path.write_text("Key;Value\ndefault_risk_pct;1.0\n")
        
        # Empty XML
        trades_path = project_root / "trades.xml"
        trades_path.write_text("<TradeLog><Trades></Trades></TradeLog>")
        
        # Journal
        journal_path = project_root / "journal.csv"
        journal_path.write_text("Date,Total Cash,Total Equity,Total Assets\n08.02.2026,10000,10000,0")
        
        # Paper Journal
        paper_journal_path = project_root / "paper_journal.csv"
        paper_journal_path.write_text("Date;Total Cash;Total Equity;Total Assets\n08.02.2026;10000;10000;0")
        
        return project_root

    def test_paper_position_manual_override(self, setup_project):
        """Verifies that manual quantity override is respected by add_paper_position."""
        service = PortfolioService(project_root=str(setup_project), context="paper")
        
        # Scenario: 
        # Equity 10000, Risk 1% = 100$. Entry 100, Stop 90 (Risk/Share 10). 
        # Calculated Qty by Service Logic would be = 100 / 10 = 10 shares.
        # User manual override = 50 shares (Aggressive).
        
        res = service.add_paper_position(
            symbol="OVERRIDE", 
            entry_price=100.0, 
            stop_loss=90.0, 
            risk_pct=1.0, 
            quantity=50
        )
        
        # Check return dict
        assert res['qty'] == 50, f"Expected 50, got {res['qty']}"
        assert res['symbol'] == "OVERRIDE"
        
        # Check XML persistence via Service
        positions = service.get_open_positions()
        # Find the position
        pos = next((p for p in positions if p.symbol == "OVERRIDE"), None)
        assert pos is not None
        assert pos.quantity == 50.0
