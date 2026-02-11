import pytest
import os
import csv
from py_manage_portfolio.service import PortfolioService
from py_riskmanagement import MinerviniSizer, TradeParameters, SizingContext

class TestMinerviniSizingWizard:
    @pytest.fixture
    def setup_project(self, tmp_path):
        """Creates a temporary project structure with risk settings and journal."""
        project_root = tmp_path
        
        # Create data_risksettings.csv
        settings_path = project_root / "data_risksettings.csv"
        with open(settings_path, 'w', encoding='utf-8') as f:
            f.write("Key;Value\n")
            f.write("default_risk_pct;1.0\n")
            f.write("max_pos_size_pct;25.0\n")
            f.write("default_fee;5.0\n")
            f.write("max_equity_risk;1.25\n")
        
        # Create empty trades.xml
        trades_path = project_root / "trades.xml"
        trades_path.write_text("<TradeLog><Trades></Trades></TradeLog>")
        
        # Create minimal journal.csv
        journal_path = project_root / "journal.csv"
        journal_path.write_text("Date,Total Cash,Total Equity,Total Assets\n08.02.2026,10000,10000,0")
        
        return project_root

    def test_sizer_funnel_logic_risk_bottleneck(self, setup_project):
        """Verifies the funnel logic when RISK is the limiting factor."""
        sizer = MinerviniSizer(str(setup_project))
        
        # Equity 10000, Risk 1% = 100$. Fees (2x5$) = 10$. Net Risk Budget = 90$.
        # Entry 100, Stop 90 -> Risk/Share = 10$. 
        # Suggested = floor(90/10) = 9 shares.
        ctx = sizer.calculate_wallet_context(equity=10000.0, current_exposure=0.0, target_exposure_pct=100.0)
        params = TradeParameters(
            symbol="TEST", 
            entry_price=100.0, 
            stop_loss=90.0, 
            risk_pct=1.0, 
            max_position_pct=25.0, 
            one_way_fee=5.0
        )
        
        result = sizer.calculate_sizing(ctx, params)
        assert result.suggested_shares == 9
        assert result.bottleneck == "RISK"
        assert result.limit_risk_shares == 9
        assert result.limit_size_shares == 25 # (0.25 * 10000) / 100

    def test_sizer_funnel_logic_size_bottleneck(self, setup_project):
        """Verifies the funnel logic when SIZE CAP (Max Position) is the limiting factor."""
        sizer = MinerviniSizer(str(setup_project))
        
        # Tight Stop -> Risk allows many shares.
        # Entry 100, Stop 99.5 -> Risk/Share = 0.5. Net Risk = 90. 
        # Risk Limit: 90 / 0.5 = 180 shares.
        # Size Limit: 25% of 10000 = 2500$ = 25 shares.
        ctx = sizer.calculate_wallet_context(equity=10000.0, current_exposure=0.0, target_exposure_pct=100.0)
        params = TradeParameters(
            symbol="TEST", 
            entry_price=100.0, 
            stop_loss=99.5, 
            risk_pct=1.0, 
            max_position_pct=25.0, 
            one_way_fee=5.0
        )
        
        result = sizer.calculate_sizing(ctx, params)
        assert result.suggested_shares == 25
        assert result.bottleneck == "SIZE CAP"

    def test_sizer_funnel_logic_budget_bottleneck(self, setup_project):
        """Verifies the funnel logic when BUDGET (Exposure) is the limiting factor."""
        sizer = MinerviniSizer(str(setup_project))
        
        # High exposure already, small budget left.
        # Current exposure: 9000. Target: 100% (10000). Available: 1000.
        # Entry 100 -> Budget shares = 10.
        # Risk allows 90 shares (same as above).
        # Size cap allows 25 shares.
        ctx = sizer.calculate_wallet_context(equity=10000.0, current_exposure=9000.0, target_exposure_pct=100.0)
        params = TradeParameters(
            symbol="TEST", 
            entry_price=100.0, 
            stop_loss=99.0, 
            risk_pct=1.0, 
            max_position_pct=25.0, 
            one_way_fee=5.0
        )
        
        result = sizer.calculate_sizing(ctx, params)
        assert result.suggested_shares == 10
        assert result.bottleneck == "BUDGET"

    def test_sizing_metrics_and_scenarios(self, setup_project):
        """Verifies metrics (Invested Amount, Risk Equity %) and Scenarios (BE, 2R)."""
        sizer = MinerviniSizer(str(setup_project))
        ctx = sizer.calculate_wallet_context(10000.0, 0.0, 100.0)
        # 9 shares @ 100 = 900 USD. 
        # Fees = 10 USD.
        # Total Risk = (100 - 90) * 9 + 10 = 100 USD.
        # Risk Equity % = 100 / 10000 = 1.0%
        params = TradeParameters("AAPL", 100.0, 90.0, 1.0, 25.0, 5.0)
        
        result = sizer.calculate_sizing(ctx, params)
        
        assert result.invested_amount == 900.0
        assert result.invested_pct == 9.0
        assert result.risk_amount == 100.0
        assert result.risk_equity_pct == 1.0
        
        # Scenarios
        # Breakeven: (900 + 10) / 9 = 101.111...
        assert pytest.approx(result.price_breakeven, 0.01) == 101.11
        # 2R: Entry + 2 * (Entry - Stop) = 100 + 2*10 = 120
        assert result.price_2r == 120.0
        assert result.price_3r == 130.0

    def test_portfolio_service_settings_loading(self, setup_project):
        """Verifies that the PortfolioService correctly loads settings from the CSV."""
        service = PortfolioService(project_root=str(setup_project))
        settings = service.get_risk_settings()
        
        # get_risk_settings returns a stub dict, verify it returns a dict with expected key
        assert isinstance(settings, dict)
        assert "max_pos_size_pct" in settings
        assert settings["max_pos_size_pct"] == 25.0

    def test_wallet_context_calculation(self, setup_project):
        """Tests the available budget calculation in wallet context."""
        sizer = MinerviniSizer(str(setup_project))
        
        # Target 120% of 10000 = 12000.
        # Current exposure 5000.
        # Available = 7000.
        ctx = sizer.calculate_wallet_context(equity=10000.0, current_exposure=5000.0, target_exposure_pct=120.0)
        
        assert ctx.available_budget == 7000.0
        assert ctx.target_exposure_pct == 120.0
    def test_paper_journal_persistence(self, setup_project):
        """Verifies that paper metrics can be saved and reloaded."""
        service = PortfolioService(project_root=str(setup_project), context="sim")
        
        # update_paper_journal uses keyword 'exposure' (not 'assets')
        service.update_paper_journal(equity=15000.0, exposure=5000.0)
        
        # _get_journal_metrics recalculates equity = cash + position_exposure
        # Cash was set to 15000 - 5000 = 10000. No positions → exposure=0 → equity = cash
        equity, cash, exposure = service._get_journal_metrics()
        
        assert cash == 10000.0  # Cash = Equity - Exposure = 15000 - 5000

    def test_unified_journal_metrics_from_state(self, setup_project):
        """Verifies that _get_journal_metrics returns values from PortfolioState."""
        service = PortfolioService(project_root=str(setup_project), context="sim")
        
        # Initial state should have defaults (100k cash, 100k equity)
        equity, cash, exposure = service._get_journal_metrics()
        
        assert equity > 0
        assert cash >= 0
        assert exposure >= 0
