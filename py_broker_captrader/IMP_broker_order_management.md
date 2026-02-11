# Implementation Plan: Broker Order Management (IMP_broker_order_management.md)

## Context
The user requires methods to retrieve detailed open orders (with status, fill tracking, and position reference) and to place new orders (with type, validity, price parameters) programmatically via the Broker Interface.

## 1. System Skeleton (Shared Context)

### 1.1 Data Structures
We must update `OpenOrder` to include status and position reference fields and define an `OrderRequest` structure for placing orders.

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class OrderStatus(Enum):
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    UNKNOWN = "Unknown"

@dataclass
class OpenOrder:
    """Detailed open order information."""
    symbol: str  # Functions as Position Reference (F-API-090)
    order_id: str
    order_type: str    # e.g., 'LMT', 'STP', 'STP LMT'
    action: str        # 'BUY' or 'SELL'
    quantity: float
    filled_quantity: float = 0.0  # F-API-070
    status: OrderStatus = OrderStatus.PRE_SUBMITTED # F-API-070
    time_in_force: str = "DAY" # F-API-080
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
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
```

### 1.2 Interface Updates
A new interface `OrderManager` will be created to handle order placement. `PortfolioReader` will be updated to include `get_open_orders` with the richer return type.

```python
from abc import ABC, abstractmethod
from typing import List

class PortfolioReader(ABC):
    # ... existing methods ...
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OpenOrder]:
        """Get all open orders, optionally filtered by symbol."""
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
```

## 2. Implementation Work Orders

### Task T-001: Skeleton Update
**Target File:** `py_manage_portfolio/data_source.py`
**Description:** Update `OpenOrder` dataclass, add `OrderStatus` enum, `OrderRequest` dataclass, and define `OrderManager` interface.
**Code Stub:**
```python
from enum import Enum
# ... other imports

class OrderStatus(Enum):
    # ... (as defined in Skeleton)

@dataclass
class OpenOrder:
    # ... (updated fields from Skeleton)

@dataclass
class OrderRequest:
    # ... (as defined in Skeleton)

class OrderManager(ABC):
    @abstractmethod
    def place_order(self, request: OrderRequest) -> Optional[str]:
        """Places a new order at the broker."""
        pass
```

### Task T-002: Broker Implementation (Getter)
**Target File:** `py_broker_captrader/broker_data_source.py`
**Description:** Update `get_open_orders` to map IBKR order status to `OrderStatus` enum and populate `filled_quantity`.
**Context:** Uses `ib.openTrades()`.
**Code Stub:**
```python
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OpenOrder]:
        """
        Fetches open orders and maps them to OpenOrder DTOs.
        Maps IBKR status to OrderStatus enum.
        Sets filled_quantity from order.filled.
        """
        # TODO: Implement logic using self._connection.ib.openTrades()
        pass
```
**Algo/Logic Steps:**
1. Call `ib.openTrades()`.
2. Iterate through trades.
3. Map `trade.orderStatus.status` to `OrderStatus` (default to `PRE_SUBMITTED` if unsure).
   - IBKR statuses: `PendingSubmit`, `PreSubmitted`, `Submitted`, `ApiCancelled`, `Cancelled`, `Filled`, `Inactive`.
4. Extract `filled` quantity from `trade.orderStatus.filled`.
5. Construct and return `OpenOrder` list.

### Task T-003: Broker Implementation (Placer)
**Target File:** `py_broker_captrader/broker_data_source.py`
**Description:** Implement `OrderManager` interface in `BrokerDataSource`. Implement `place_order`.
**Context:** Uses `ib.placeOrder`.
**Code Stub:**
```python
class BrokerDataSource(PortfolioReader, ConnectionAware, OrderManager): # Add inheritance
    # ...
    def place_order(self, request: OrderRequest) -> Optional[str]:
        """
        Creates and places an IBKR order based on OrderRequest.
        """
        # TODO: Implement logic
        pass
```
**Algo/Logic Steps:**
1. Create `ib_insync.Contract` (Stock) for `request.symbol`.
2. Qualify contract using `ib.qualifyContracts`.
3. Create `ib_insync.Order`:
   - Set `action`, `totalQuantity`, `orderType`.
   - Set `lmtPrice` if limit.
   - Set `auxPrice` if stop.
   - Set `tif` (Time in Force).
4. Call `ib.placeOrder(contract, order)`.
5. Return `str(trade.order.orderId)` if trade object is returned, else `None`.

### Task T-004: Offline Implementation Update
**Target File:** `py_manage_portfolio/offline_data_source.py`
**Description:** Update `OfflineDataSource` to implement `OrderManager` (as no-op or sim) and update `get_open_orders` to match new DTO structure.
**Context:** `place_order` in offline mode can either be a no-op returning `None` or just log a warning (since it's not a simulation engine yet, just a viewer/logger).
**Code Stub:**
```python
class OfflineDataSource(PortfolioReader, PortfolioWriter, OrderManager): # Add inheritance
    # ...
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OpenOrder]:
        # Update existing mapping to include status=PRE_SUBMITTED and filled=0
        pass

    def place_order(self, request: OrderRequest) -> Optional[str]:
        print(f"⚠️ Simulation Order Placement not fully implemented. Request: {request}")
        return "SIM_ORDER_ID"
```
