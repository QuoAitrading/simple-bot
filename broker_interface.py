"""
Broker Interface Abstraction Layer
Provides clean separation between trading strategy and broker execution.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging
import time
import random


logger = logging.getLogger(__name__)


class BrokerInterface(ABC):
    """
    Abstract base class for broker operations.
    Allows swapping brokers without changing strategy code.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to broker and authenticate.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker."""
        pass
    
    @abstractmethod
    def get_account_equity(self) -> float:
        """
        Get current account equity.
        
        Returns:
            Account equity in dollars
        """
        pass
    
    @abstractmethod
    def get_position_quantity(self, symbol: str) -> int:
        """
        Get current position quantity for symbol.
        
        Args:
            symbol: Instrument symbol
        
        Returns:
            Position quantity (positive for long, negative for short, 0 for flat)
        """
        pass
    
    @abstractmethod
    def place_market_order(self, symbol: str, side: str, quantity: int) -> Optional[Dict[str, Any]]:
        """
        Place a market order.
        
        Args:
            symbol: Instrument symbol
            side: Order side ("BUY" or "SELL")
            quantity: Number of contracts
        
        Returns:
            Order details if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def place_limit_order(self, symbol: str, side: str, quantity: int, 
                         limit_price: float) -> Optional[Dict[str, Any]]:
        """
        Place a limit order.
        
        Args:
            symbol: Instrument symbol
            side: Order side ("BUY" or "SELL")
            quantity: Number of contracts
            limit_price: Limit price
        
        Returns:
            Order details if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def place_stop_order(self, symbol: str, side: str, quantity: int, 
                        stop_price: float) -> Optional[Dict[str, Any]]:
        """
        Place a stop order.
        
        Args:
            symbol: Instrument symbol
            side: Order side ("BUY" or "SELL")
            quantity: Number of contracts
            stop_price: Stop price
        
        Returns:
            Order details if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def subscribe_market_data(self, symbol: str, callback: Callable[[str, float, int, int], None]) -> None:
        """
        Subscribe to real-time market data.
        
        Args:
            symbol: Instrument symbol
            callback: Function to call with tick data (symbol, price, volume, timestamp)
        """
        pass
    
    @abstractmethod
    def fetch_historical_bars(self, symbol: str, timeframe: int, count: int) -> list:
        """
        Fetch historical bars.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe in minutes
            count: Number of bars to fetch
        
        Returns:
            List of bar dictionaries
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if broker connection is active.
        
        Returns:
            True if connected
        """
        pass


class MockBroker(BrokerInterface):
    """
    Mock broker implementation for testing.
    Simulates order fills with realistic delays.
    """
    
    def __init__(self, starting_equity: float = 10000.0, fill_delay: float = 0.1):
        """
        Initialize mock broker.
        
        Args:
            starting_equity: Starting account equity
            fill_delay: Simulated order fill delay in seconds
        """
        self.starting_equity = starting_equity
        self.current_equity = starting_equity
        self.fill_delay = fill_delay
        self.positions: Dict[str, int] = {}
        self.connected = False
        self.order_counter = 0
        
        # Configurable scenarios
        self.simulate_failures = False
        self.failure_rate = 0.1  # 10% failure rate when enabled
    
    def connect(self) -> bool:
        """Connect to mock broker."""
        logger.info("Connecting to mock broker...")
        time.sleep(0.1)  # Simulate connection delay
        self.connected = True
        logger.info(f"Mock broker connected. Starting equity: ${self.starting_equity:.2f}")
        return True
    
    def disconnect(self) -> None:
        """Disconnect from mock broker."""
        logger.info("Disconnecting from mock broker...")
        self.connected = False
        logger.info("Mock broker disconnected")
    
    def get_account_equity(self) -> float:
        """Get current account equity."""
        return self.current_equity
    
    def get_position_quantity(self, symbol: str) -> int:
        """Get current position quantity."""
        return self.positions.get(symbol, 0)
    
    def place_market_order(self, symbol: str, side: str, quantity: int) -> Optional[Dict[str, Any]]:
        """Place a market order."""
        if not self.connected:
            logger.error("Cannot place order: not connected")
            return None
        
        # Simulate failures if enabled
        if self.simulate_failures and random.random() < self.failure_rate:
            logger.error("Mock order failed (simulated failure)")
            return None
        
        # Simulate fill delay
        time.sleep(self.fill_delay)
        
        # Update position
        current_pos = self.positions.get(symbol, 0)
        if side == "BUY":
            self.positions[symbol] = current_pos + quantity
        else:  # SELL
            self.positions[symbol] = current_pos - quantity
        
        self.order_counter += 1
        order = {
            "order_id": f"MOCK{self.order_counter:06d}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "MARKET",
            "status": "FILLED",
            "filled_quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Mock market order filled: {side} {quantity} {symbol}")
        return order
    
    def place_limit_order(self, symbol: str, side: str, quantity: int, 
                         limit_price: float) -> Optional[Dict[str, Any]]:
        """Place a limit order."""
        if not self.connected:
            logger.error("Cannot place order: not connected")
            return None
        
        # Simulate failures if enabled
        if self.simulate_failures and random.random() < self.failure_rate:
            logger.error("Mock order failed (simulated failure)")
            return None
        
        # Simulate fill delay (slightly longer for limit orders)
        time.sleep(self.fill_delay * 1.5)
        
        # Update position
        current_pos = self.positions.get(symbol, 0)
        if side == "BUY":
            self.positions[symbol] = current_pos + quantity
        else:  # SELL
            self.positions[symbol] = current_pos - quantity
        
        self.order_counter += 1
        order = {
            "order_id": f"MOCK{self.order_counter:06d}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "LIMIT",
            "limit_price": limit_price,
            "status": "FILLED",
            "filled_quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Mock limit order filled: {side} {quantity} {symbol} @ {limit_price:.2f}")
        return order
    
    def place_stop_order(self, symbol: str, side: str, quantity: int, 
                        stop_price: float) -> Optional[Dict[str, Any]]:
        """Place a stop order."""
        if not self.connected:
            logger.error("Cannot place order: not connected")
            return None
        
        # Simulate failures if enabled
        if self.simulate_failures and random.random() < self.failure_rate:
            logger.error("Mock order failed (simulated failure)")
            return None
        
        # Simulate fill delay
        time.sleep(self.fill_delay)
        
        # Update position
        current_pos = self.positions.get(symbol, 0)
        if side == "BUY":
            self.positions[symbol] = current_pos + quantity
        else:  # SELL
            self.positions[symbol] = current_pos - quantity
        
        self.order_counter += 1
        order = {
            "order_id": f"MOCK{self.order_counter:06d}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "STOP",
            "stop_price": stop_price,
            "status": "FILLED",
            "filled_quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Mock stop order filled: {side} {quantity} {symbol} @ {stop_price:.2f}")
        return order
    
    def subscribe_market_data(self, symbol: str, callback: Callable[[str, float, int, int], None]) -> None:
        """Subscribe to market data (mock implementation)."""
        logger.info(f"Mock market data subscription for {symbol} - callback registered")
        # In a real implementation, this would start a data feed
        # For mock, we just log the subscription
    
    def fetch_historical_bars(self, symbol: str, timeframe: int, count: int) -> list:
        """Fetch historical bars (mock implementation)."""
        logger.info(f"Fetching {count} mock historical bars for {symbol} ({timeframe}min)")
        # Return empty list - mock broker doesn't provide historical data
        return []
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.connected
    
    def set_failure_simulation(self, enabled: bool, rate: float = 0.1) -> None:
        """
        Enable/disable failure simulation for testing.
        
        Args:
            enabled: Whether to simulate failures
            rate: Failure rate (0.0 to 1.0)
        """
        self.simulate_failures = enabled
        self.failure_rate = rate
        logger.info(f"Mock broker failure simulation: {'enabled' if enabled else 'disabled'} (rate={rate})")


class TopStepBroker(BrokerInterface):
    """
    TopStep SDK broker implementation.
    Wraps TopStep API calls with error handling and retry logic.
    """
    
    def __init__(self, api_token: str, max_retries: int = 3, timeout: int = 30):
        """
        Initialize TopStep broker.
        
        Args:
            api_token: TopStep API token
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.api_token = api_token
        self.max_retries = max_retries
        self.timeout = timeout
        self.connected = False
        self.circuit_breaker_open = False
        self.failure_count = 0
        self.circuit_breaker_threshold = 5
        
        # SDK client (will be initialized on connect)
        self.sdk_client = None
    
    def connect(self) -> bool:
        """Connect to TopStep SDK."""
        if self.circuit_breaker_open:
            logger.error("Circuit breaker is open - cannot connect")
            return False
        
        try:
            logger.info("Connecting to TopStep SDK...")
            # TODO: Initialize actual SDK client
            # from topstep_sdk import TopStepClient
            # self.sdk_client = TopStepClient(api_token=self.api_token, timeout=self.timeout)
            # self.connected = self.sdk_client.connect()
            
            # Placeholder implementation
            logger.warning("TopStep SDK not yet integrated - using placeholder")
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to TopStep SDK: {e}")
            self._record_failure()
            return False
    
    def disconnect(self) -> None:
        """Disconnect from TopStep SDK."""
        try:
            if self.sdk_client:
                # TODO: Actual SDK disconnect
                # self.sdk_client.disconnect()
                pass
            self.connected = False
            logger.info("Disconnected from TopStep SDK")
        except Exception as e:
            logger.error(f"Error disconnecting from TopStep SDK: {e}")
    
    def get_account_equity(self) -> float:
        """Get account equity from TopStep."""
        if not self.connected:
            logger.error("Cannot get equity: not connected")
            return 0.0
        
        try:
            # TODO: Actual SDK call
            # return self.sdk_client.get_account_equity()
            logger.warning("TopStep SDK not integrated - returning placeholder value")
            return 0.0
        except Exception as e:
            logger.error(f"Error getting account equity: {e}")
            self._record_failure()
            return 0.0
    
    def get_position_quantity(self, symbol: str) -> int:
        """Get position quantity from TopStep."""
        if not self.connected:
            logger.error("Cannot get position: not connected")
            return 0
        
        try:
            # TODO: Actual SDK call
            # return self.sdk_client.get_position_quantity(symbol)
            logger.warning("TopStep SDK not integrated - returning 0")
            return 0
        except Exception as e:
            logger.error(f"Error getting position quantity: {e}")
            self._record_failure()
            return 0
    
    def place_market_order(self, symbol: str, side: str, quantity: int) -> Optional[Dict[str, Any]]:
        """Place market order through TopStep SDK."""
        if not self.connected:
            logger.error("Cannot place order: not connected")
            return None
        
        for attempt in range(self.max_retries):
            try:
                # TODO: Actual SDK call
                # order = self.sdk_client.place_market_order(symbol=symbol, side=side, quantity=quantity)
                # return order
                logger.warning("TopStep SDK not integrated - order not placed")
                return None
            except Exception as e:
                logger.error(f"Error placing market order (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                else:
                    self._record_failure()
        
        return None
    
    def place_limit_order(self, symbol: str, side: str, quantity: int, 
                         limit_price: float) -> Optional[Dict[str, Any]]:
        """Place limit order through TopStep SDK."""
        if not self.connected:
            logger.error("Cannot place order: not connected")
            return None
        
        for attempt in range(self.max_retries):
            try:
                # TODO: Actual SDK call
                # order = self.sdk_client.place_limit_order(
                #     symbol=symbol, side=side, quantity=quantity, limit_price=limit_price
                # )
                # return order
                logger.warning("TopStep SDK not integrated - order not placed")
                return None
            except Exception as e:
                logger.error(f"Error placing limit order (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    self._record_failure()
        
        return None
    
    def place_stop_order(self, symbol: str, side: str, quantity: int, 
                        stop_price: float) -> Optional[Dict[str, Any]]:
        """Place stop order through TopStep SDK."""
        if not self.connected:
            logger.error("Cannot place order: not connected")
            return None
        
        for attempt in range(self.max_retries):
            try:
                # TODO: Actual SDK call
                # order = self.sdk_client.place_stop_order(
                #     symbol=symbol, side=side, quantity=quantity, stop_price=stop_price
                # )
                # return order
                logger.warning("TopStep SDK not integrated - order not placed")
                return None
            except Exception as e:
                logger.error(f"Error placing stop order (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    self._record_failure()
        
        return None
    
    def subscribe_market_data(self, symbol: str, callback: Callable[[str, float, int, int], None]) -> None:
        """Subscribe to market data through TopStep SDK."""
        if not self.connected:
            logger.error("Cannot subscribe: not connected")
            return
        
        try:
            # TODO: Actual SDK call
            # self.sdk_client.subscribe_market_data(symbol=symbol, callback=callback)
            logger.warning("TopStep SDK not integrated - subscription not active")
        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}")
            self._record_failure()
    
    def fetch_historical_bars(self, symbol: str, timeframe: int, count: int) -> list:
        """Fetch historical bars through TopStep SDK."""
        if not self.connected:
            logger.error("Cannot fetch bars: not connected")
            return []
        
        try:
            # TODO: Actual SDK call
            # return self.sdk_client.fetch_historical_bars(symbol=symbol, timeframe=timeframe, count=count)
            logger.warning("TopStep SDK not integrated - returning empty list")
            return []
        except Exception as e:
            logger.error(f"Error fetching historical bars: {e}")
            self._record_failure()
            return []
    
    def is_connected(self) -> bool:
        """Check if connected to TopStep SDK."""
        return self.connected and not self.circuit_breaker_open
    
    def _record_failure(self) -> None:
        """Record a failure and potentially open circuit breaker."""
        self.failure_count += 1
        if self.failure_count >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            logger.critical(f"Circuit breaker opened after {self.failure_count} failures")
    
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker (manual recovery)."""
        self.circuit_breaker_open = False
        self.failure_count = 0
        logger.info("Circuit breaker reset")


def create_broker(broker_type: str, api_token: Optional[str] = None, 
                 starting_equity: float = 10000.0) -> BrokerInterface:
    """
    Factory function to create broker instance.
    
    Args:
        broker_type: Type of broker ("mock" or "topstep")
        api_token: API token for TopStep (required if broker_type is "topstep")
        starting_equity: Starting equity for mock broker
    
    Returns:
        Broker instance
    
    Raises:
        ValueError: If invalid broker type or missing API token
    """
    if broker_type == "mock":
        return MockBroker(starting_equity=starting_equity)
    elif broker_type == "topstep":
        if not api_token:
            raise ValueError("API token is required for TopStep broker")
        return TopStepBroker(api_token=api_token)
    else:
        raise ValueError(f"Unknown broker type: {broker_type}")
