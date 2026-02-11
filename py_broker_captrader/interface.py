"""
Broker Interface — Re-exports from py_manage_portfolio.data_source.

The canonical interface definitions live in py_manage_portfolio.data_source.
This file provides backward-compatible aliases so existing broker code
can continue to use the Broker* naming convention.
"""
from py_manage_portfolio.data_source import (
    PortfolioReader as BrokerReader,
    ConnectionAware as BrokerConnection,
    OrderManager as BrokerOrderManager,
    OpenOrder as BrokerOpenOrder,
    OrderRequest as BrokerOrderRequest,
    OrderStatus,
)
