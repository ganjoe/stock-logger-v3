"""
Portfolio Data Source Interfaces and DTOs.

This module defines segregated interfaces for portfolio data sources:

- PortfolioReader: Read-only portfolio state access (get_portfolio_state)
- ConnectionAware: Lifecycle management for broker connections
- OrderManager: Interface for placing and modifying orders
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .models.portfolio_state import PortfolioState


class OrderStatus(Enum):
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    UNKNOWN = "Unknown"


@dataclass
class OpenOrder:
    """Detailed open order information."""
    symbol: str
    order_type: str    # e.g., 'LMT', 'STP', 'STP LMT'
    action: str        # 'BUY' or 'SELL'
    quantity: float
    time_in_force: str  # e.g., 'GTC', 'DAY'
    order_id: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: float = 0.0
    status: OrderStatus = OrderStatus.PRE_SUBMITTED


@dataclass
class OrderRequest:
    """Parameters for placing a new order."""
    symbol: str
    action: str        # 'BUY' or 'SELL'
    quantity: float
    order_type: str    # 'LMT', 'MKT', 'STP', 'STP LMT'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY" # 'DAY', 'GTC'


class PortfolioReader(ABC):
    """
    Read-only portfolio access interface.
    """
    
    @abstractmethod
    def get_portfolio_state(self) -> PortfolioState:
        """Get consolidated portfolio state (cash, equity, positions with prices)."""
        pass


class OrderManager(ABC):
    """Interface for placing and modifying orders (F-API-090)."""
    
    @abstractmethod
    def place_order(self, request: OrderRequest) -> Optional[str]:
        """
        Places a new order at the broker.
        Returns the Order ID on success, or None on failure.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancels an existing order by ID.
        Returns True if cancellation request was sent.
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OpenOrder]:
        """Get all open orders, optionally filtered by symbol."""
        pass


class ConnectionAware(ABC):
    """
    Lifecycle management for data sources with external connections.
    """
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the connection is active."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        pass
