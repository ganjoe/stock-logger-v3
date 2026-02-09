"""
Portfolio Data Source Interface and DTOs.

This module defines the abstract interface for portfolio data sources,
allowing the PortfolioService to work with different backends (Offline files, Broker API).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional


@dataclass
class AccountMetrics:
    """Account-level financial metrics."""
    equity: float
    cash: float
    exposure: float  # Total invested / market value of positions


@dataclass
class RawPosition:
    """A position as returned by the data source (before enrichment with market data)."""
    symbol: str
    isin: Optional[str]
    quantity: float
    entry_price: float
    entry_date: Optional[date]
    currency: str


@dataclass
class StopOrder:
    """Stop-loss order or risk data."""
    symbol: str
    stop_price: float
    order_id: Optional[str] = None  # For broker stops
    initial_risk: Optional[float] = None  # For offline risk data


class PortfolioDataSource(ABC):
    """
    Abstract interface for portfolio data sources.
    
    Implementations:
    - OfflineDataSource: Reads from trades.xml, manual_risk_data.json, journal.csv
    - BrokerDataSource: Reads from IBKR API (future)
    """
    
    @abstractmethod
    def get_positions(self) -> List[RawPosition]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    def get_stop_losses(self) -> Dict[str, StopOrder]:
        """Get stop-loss data keyed by symbol."""
        pass
    
    @abstractmethod
    def get_account_metrics(self) -> AccountMetrics:
        """Get account-level metrics (equity, cash, exposure)."""
        pass
    
    @abstractmethod
    def set_stop_loss(self, symbol: str, stop_price: float) -> bool:
        """Set or update a stop-loss. Returns True on success."""
        pass
    
    @abstractmethod
    def close_position(self, symbol: str) -> bool:
        """Close/delete a position. Returns True on success."""
        pass
    
    def add_position(self, symbol: str, entry_price: float, stop_loss: float, 
                     quantity: float, **kwargs) -> dict:
        """
        Add a new position (for paper/offline trading only).
        Broker implementations should raise NotImplementedError.
        """
        raise NotImplementedError("add_position not supported by this data source")
