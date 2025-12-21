"""
Signal Protocol - How trades are communicated between Master and Followers
Uses your existing Flask API as the relay server
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json


@dataclass
class TradeSignal:
    """A trade signal from Master to Followers"""
    signal_id: str           # Unique ID for this signal
    timestamp: str           # ISO format timestamp
    action: str              # "OPEN", "CLOSE", "FLATTEN"
    symbol: str              # e.g. "MES", "NQ"
    side: str                # "BUY" or "SELL"
    quantity: int            # Number of contracts
    entry_price: float       # Price at which master entered
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: dict) -> "TradeSignal":
        return cls(
            signal_id=data["signal_id"],
            timestamp=data["timestamp"],
            action=data["action"],
            symbol=data["symbol"],
            side=data["side"],
            quantity=data["quantity"],
            entry_price=data["entry_price"],
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "TradeSignal":
        return cls.from_dict(json.loads(json_str))


def create_signal_id() -> str:
    """Generate a unique signal ID"""
    import uuid
    return str(uuid.uuid4())[:8]


def create_open_signal(symbol: str, side: str, quantity: int, entry_price: float,
                       stop_loss: float = None, take_profit: float = None) -> TradeSignal:
    """Create an OPEN trade signal"""
    return TradeSignal(
        signal_id=create_signal_id(),
        timestamp=datetime.now().isoformat(),
        action="OPEN",
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit
    )


def create_close_signal(symbol: str, side: str, quantity: int, exit_price: float) -> TradeSignal:
    """Create a CLOSE trade signal"""
    return TradeSignal(
        signal_id=create_signal_id(),
        timestamp=datetime.now().isoformat(),
        action="CLOSE",
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=exit_price,  # Using entry_price field for exit
        stop_loss=None,
        take_profit=None
    )


def create_flatten_signal(symbol: str) -> TradeSignal:
    """Create a FLATTEN signal (close everything)"""
    return TradeSignal(
        signal_id=create_signal_id(),
        timestamp=datetime.now().isoformat(),
        action="FLATTEN",
        symbol=symbol,
        side="FLAT",
        quantity=0,
        entry_price=0.0
    )
