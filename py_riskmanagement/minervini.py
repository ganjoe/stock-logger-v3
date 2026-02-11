"""
Minervini Position Sizing Strategy.

Implements the "Funnel" approach: Risk Limit, Budget Limit, Size Cap.
The minimum of all three determines the suggested share count.
"""
import os
import csv
import math
from typing import Dict

from .interface import RiskStrategy, SizingContext, TradeParameters, SizingResult


class MinerviniSizer(RiskStrategy):
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict:
        """Loads risk settings from data_risksettings.csv."""
        settings = {
            "default_risk_pct": 1.0,
            "max_pos_size_pct": 25.0,
            "default_fee": 2.0
        }
        path = os.path.join(self.project_root, "data_risksettings.csv")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        key = row.get("Key") or row.get("ID")
                        val = row.get("Value")
                        if key and val:
                            try:
                                if val.isdigit():
                                    settings[key] = int(val)
                                else:
                                    settings[key] = float(val.replace(',', '.'))
                            except ValueError:
                                settings[key] = val
            except:
                pass
        return settings
    
    def get_defaults(self) -> Dict:
        """Returns loaded defaults."""
        return self.settings

    def calculate_wallet_context(self, equity: float, current_exposure: float, target_exposure_pct: float) -> SizingContext:
        """Calculates available budget based on target exposure."""
        target_amount = equity * (target_exposure_pct / 100.0)
        available = target_amount - current_exposure
        return SizingContext(
            equity=equity,
            current_exposure=current_exposure,
            target_exposure_pct=target_exposure_pct,
            available_budget=available
        )

    def calculate_sizing(self, context: SizingContext, params: TradeParameters) -> SizingResult:
        """
        The Minervini Funnel: Calculates risk, budget, and size limits to suggest share count.
        """
        warnings = []
        
        # 1. Risk Limit (Net of Roundtrip Fees)
        # Risk Budget = Equity * Risk%
        risk_budget = context.equity * (params.risk_pct / 100.0)
        # Net Risk Budget = Risk Budget - (2 * OneWayFee)
        net_risk_budget = risk_budget - (2 * params.one_way_fee)
        
        risk_per_share = abs(params.entry_price - params.stop_loss)
        if risk_per_share <= 0:
            limit_risk = 0
            warnings.append("Stop Loss equals Entry Price (Risk per share is 0)")
        elif net_risk_budget <= 0:
            limit_risk = 0
            warnings.append("Risk budget consumed by fees")
        else:
            limit_risk = math.floor(net_risk_budget / risk_per_share)

        # 2. Budget Limit (Exposure)
        if context.available_budget <= 0:
             limit_budget = 0
             warnings.append("No budget available (Target Exposure reached)")
        else:
             limit_budget = math.floor(context.available_budget / params.entry_price)

        # 3. Size Scale Limit (Cap)
        max_pos_value = context.equity * (params.max_position_pct / 100.0)
        limit_size = math.floor(max_pos_value / params.entry_price)
        
        # The Funnel (Minimum of all limits)
        suggested = max(0, min(limit_risk, limit_budget, limit_size))
        
        # Identify Bottleneck
        bottleneck = "UNKNOWN"
        if suggested == limit_risk: bottleneck = "RISK"
        elif suggested == limit_size: bottleneck = "SIZE CAP"
        elif suggested == limit_budget: bottleneck = "BUDGET"
        
        # Calculate Metrics for Suggested
        invested = suggested * params.entry_price
        invested_pct = (invested / context.equity * 100) if context.equity > 0 else 0
        
        total_risk = (suggested * risk_per_share) + (2 * params.one_way_fee)
        risk_equity_pct = (total_risk / context.equity * 100) if context.equity > 0 else 0
        
        # Scenarios (Break-Even needs to cover Roundtrip Fee)
        # BE = Entry + (2*Fee / Shares)
        price_be = params.entry_price + ((2 * params.one_way_fee) / suggested) if suggested > 0 else 0
        
        # R-Multiples (Standard: Distance from Entry)
        # 2R = Entry + 2 * (Entry - Stop)
        dist = params.entry_price - params.stop_loss
        price_2r = params.entry_price + (2 * dist)
        price_3r = params.entry_price + (3 * dist)
        
        return SizingResult(
            limit_risk_shares=int(limit_risk),
            limit_budget_shares=int(limit_budget),
            limit_size_shares=int(limit_size),
            suggested_shares=int(suggested),
            bottleneck=bottleneck,
            invested_amount=invested,
            invested_pct=invested_pct,
            risk_amount=total_risk,
            risk_equity_pct=risk_equity_pct,
            price_breakeven=price_be,
            price_2r=price_2r,
            price_3r=price_3r,
            warnings=warnings
        )
