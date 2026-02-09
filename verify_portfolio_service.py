import os
import unittest
from py_manage_portfolio.service import PortfolioService

class TestPortfolioRiskSettings(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(self.project_root, "data_risksettings.csv")
        self.service = PortfolioService(self.project_root, context="live")

    def test_load_default_settings(self):
        """Tests if default settings are loaded when file is missing."""
        if os.path.exists(self.settings_file):
            os.rename(self.settings_file, self.settings_file + ".bak")
        
        try:
            settings = self.service.get_risk_settings()
            self.assertEqual(settings["holding_threshold"], 30)
            self.assertEqual(settings["default_risk_pct"], 1.0)
            self.assertEqual(settings["max_equity_risk"], 1.25)
        finally:
            if os.path.exists(self.settings_file + ".bak"):
                os.rename(self.settings_file + ".bak", self.settings_file)

    def test_load_custom_settings(self):
        """Tests if custom settings are correctly parsed from CSV."""
        with open(self.settings_file + ".test", "w", encoding="utf-8") as f:
            f.write("Key;Value;Description\n")
            f.write("holding_threshold;45;Test\n")
            f.write("default_risk_pct;0,5;Test\n")
            f.write("max_equity_risk;2.0;Test\n")
        
        if os.path.exists(self.settings_file):
            os.rename(self.settings_file, self.settings_file + ".original")
        
        os.rename(self.settings_file + ".test", self.settings_file)
        
        try:
            settings = self.service.get_risk_settings()
            self.assertEqual(settings["holding_threshold"], 45)
            self.assertEqual(settings["default_risk_pct"], 0.5)
            self.assertEqual(settings["max_equity_risk"], 2.0)
        finally:
            if os.path.exists(self.settings_file + ".original"):
                os.rename(self.settings_file + ".original", self.settings_file)
            elif os.path.exists(self.settings_file):
                os.remove(self.settings_file)

if __name__ == "__main__":
    unittest.main()
