"""
py_riskmanagement — Position Sizing & Risk Management Strategies.

Standalone module providing risk calculation strategies (e.g., Minervini Funnel).
No external project dependencies — pure math.
"""
from .interface import SizingContext, TradeParameters, SizingResult, RiskStrategy
from .minervini import MinerviniSizer
