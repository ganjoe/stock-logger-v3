    def test_paper_journal_persistence(self, setup_project):
        """Verifies that paper metrics can be saved and reloaded."""
        service = PortfolioService(project_root=str(setup_project), context="paper")
        
        # Initial state should be empty or defaults, but we want to test update_paper_journal
        # Directly call update_paper_journal
        service.update_paper_journal(equity=15000.0, assets=5000.0)
        
        # Verify file content
        paper_journal_path = setup_project / "paper_journal.csv"
        assert paper_journal_path.exists()
        
        content = paper_journal_path.read_text(encoding='utf-8')
        assert "Date;Equity;Cash;Total_Assets" in content
        assert "15000.00;10000.00;5000.00" in content # Cash = Equity - Assets
        
        # Verify reload via service
        # Re-initialize to ensure fresh read
        service_reload = PortfolioService(project_root=str(setup_project), context="paper")
        equity, cash, assets = service_reload._get_journal_metrics()
        
        assert equity == 15000.0
        assert assets == 5000.0
        assert cash == 10000.0

    def test_unified_journal_parsing_custom_order(self, setup_project):
        """Verifies that _get_journal_metrics parses headers correctly with mixed column order."""
        # Create a custom journal with weird column order
        custom_journal = setup_project / "custom_journal.csv"
        custom_journal.write_text("Date;Total_Assets;Cash;Equity\n2026-02-08;2000;3000;5000", encoding='utf-8')
        
        # Init service and hijack journal_file path
        service = PortfolioService(project_root=str(setup_project), context="live")
        service.journal_file = str(custom_journal)
        
        equity, cash, assets = service._get_journal_metrics()
        
        assert equity == 5000.0
        assert cash == 3000.0
        assert assets == 2000.0
