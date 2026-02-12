"""
IBKR Connection Management.

Handles connection to TWS/IB Gateway with retry logic.
"""
import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class ConnectionConfig:
    """Configuration for IBKR connection."""
    host: str = "127.0.0.1"
    port: int = 7497  # 7497 for TWS Paper, 7496 for TWS Live, 4001/4002 for Gateway
    client_id: int = 1
    timeout: int = 10
    retry_count: int = 3
    retry_delay: float = 2.0


class IBKRConnection:
    """
    Manages connection to IBKR TWS/Gateway.
    
    Uses ib_insync library for API communication.
    Connection is authenticated via TWS/Gateway (no credentials in code).
    """
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self._ib = None
        self._connected = False
    
    def connect(self) -> bool:
        """
        Connect to TWS/Gateway with retry logic.
        
        Returns:
            True if connected successfully.
            
        Raises:
            ConnectionError: If connection fails after all retries.
        """
        try:
            from ib_insync import IB
        except ImportError:
            raise ImportError(
                "ib_insync is required for broker integration. "
                "Install with: pip install ib_insync"
            )
        
        self._ib = IB()
        
        for attempt in range(1, self.config.retry_count + 1):
            try:
                self._ib.connect(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id,
                    timeout=self.config.timeout
                )
                self._connected = True
                return True
            except Exception as e:
                if attempt < self.config.retry_count:
                    time.sleep(self.config.retry_delay)
                else:
                    err_msg = str(e)
                    if "Connection refused" in err_msg:
                        detail = "Connection refused (Check 'Enable API' settings in TWS/Gateway)"
                    elif "timeout" in err_msg.lower():
                        detail = "Connection timeout (Check Host/Port and Firewall)"
                    else:
                        detail = err_msg
                        
                    raise ConnectionError(
                        f"Failed to connect to IBKR at {self.config.host}:{self.config.port} "
                        f"after {self.config.retry_count} attempts. Details: {detail}"
                    )
        
        return False
    
    def disconnect(self):
        """Disconnect from TWS/Gateway."""
        if self._ib and self._connected:
            self._ib.disconnect()
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected and self._ib is not None and self._ib.isConnected()
    
    @property
    def ib(self):
        """Get the IB instance for API calls."""
        if not self.is_connected():
            raise RuntimeError("Not connected to IBKR. Call connect() first.")
        return self._ib
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
