"""
Position Monitor - Watches your broker account for position changes
When you open/close trades, it broadcasts to all followers
"""

import asyncio
import logging
from typing import Dict, Optional, Set
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a position on your account"""
    symbol: str
    side: str  # 'long' or 'short'
    quantity: int
    entry_price: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PositionMonitor:
    """
    Monitors your broker account for position changes.
    When you manually trade, it detects the change and broadcasts to followers.
    """
    
    def __init__(self, broker, broadcaster, poll_interval: float = 0.5):
        """
        Args:
            broker: Connected broker instance (your master account)
            broadcaster: SignalBroadcaster to send signals to followers
            poll_interval: How often to check for position changes (seconds)
        """
        self.broker = broker
        self.broadcaster = broadcaster
        self.poll_interval = poll_interval
        
        # Track known positions
        self.known_positions: Dict[str, Position] = {}
        self.monitoring = False
        self._monitor_task = None
        
    async def start(self):
        """Start monitoring for position changes"""
        self.monitoring = True
        
        # Get initial positions
        await self._sync_positions()
        
        # Start monitoring loop
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("👁️  Position monitor started - watching for your trades")
        
    async def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️  Position monitor stopped")
        
    async def _sync_positions(self):
        """Get current positions from broker and sync state"""
        try:
            positions = await self.broker.get_positions()
            
            self.known_positions.clear()
            for pos in positions:
                symbol = pos.get('symbol', '')
                if not symbol:
                    continue
                    
                self.known_positions[symbol] = Position(
                    symbol=symbol,
                    side='long' if pos.get('quantity', 0) > 0 else 'short',
                    quantity=abs(pos.get('quantity', 0)),
                    entry_price=pos.get('entry_price', 0)
                )
                
            logger.info(f"📊 Synced {len(self.known_positions)} positions")
            
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            
    async def _monitor_loop(self):
        """Main monitoring loop - detect position changes"""
        while self.monitoring:
            try:
                # Get current positions from broker
                current = await self._get_current_positions()
                
                # Detect changes
                await self._check_for_changes(current)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                
            await asyncio.sleep(self.poll_interval)
            
    async def _get_current_positions(self) -> Dict[str, Position]:
        """Get current positions from broker"""
        positions = {}
        
        try:
            broker_positions = await self.broker.get_positions()
            
            for pos in broker_positions:
                symbol = pos.get('symbol', '')
                quantity = pos.get('quantity', 0)
                
                if not symbol or quantity == 0:
                    continue
                    
                positions[symbol] = Position(
                    symbol=symbol,
                    side='long' if quantity > 0 else 'short',
                    quantity=abs(quantity),
                    entry_price=pos.get('entry_price', 0)
                )
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            
        return positions
        
    async def _check_for_changes(self, current: Dict[str, Position]):
        """Check for position changes and broadcast"""
        
        # Check for new positions (OPEN signals)
        for symbol, pos in current.items():
            if symbol not in self.known_positions:
                # NEW POSITION - broadcast OPEN
                logger.info(f"🆕 NEW POSITION: {pos.side.upper()} {pos.quantity} {symbol} @ {pos.entry_price}")
                
                await self.broadcaster.broadcast_open(
                    symbol=symbol,
                    side="BUY" if pos.side == "long" else "SELL",
                    quantity=pos.quantity,
                    entry_price=pos.entry_price
                )
                
            elif self.known_positions[symbol].quantity != pos.quantity:
                # QUANTITY CHANGED - partial add or partial close
                old_qty = self.known_positions[symbol].quantity
                new_qty = pos.quantity
                
                if new_qty > old_qty:
                    # Added to position
                    diff = new_qty - old_qty
                    logger.info(f"➕ ADDED: {diff} {symbol}")
                    
                    await self.broadcaster.broadcast_open(
                        symbol=symbol,
                        side="BUY" if pos.side == "long" else "SELL",
                        quantity=diff,
                        entry_price=pos.entry_price
                    )
                else:
                    # Partial close
                    diff = old_qty - new_qty
                    logger.info(f"➖ PARTIAL CLOSE: {diff} {symbol}")
                    
                    await self.broadcaster.broadcast_close(
                        symbol=symbol,
                        side="BUY" if pos.side == "long" else "SELL",
                        quantity=diff,
                        exit_price=pos.entry_price  # Best we have
                    )
                    
        # Check for closed positions (CLOSE/FLATTEN signals)
        for symbol in list(self.known_positions.keys()):
            if symbol not in current:
                # POSITION CLOSED - broadcast FLATTEN
                old_pos = self.known_positions[symbol]
                logger.info(f"🛑 CLOSED: {old_pos.side.upper()} {old_pos.quantity} {symbol}")
                
                await self.broadcaster.broadcast_flatten(symbol=symbol)
                
        # Update known positions
        self.known_positions = current
