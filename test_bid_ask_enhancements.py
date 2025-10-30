"""
Tests for Enhanced Bid/Ask Manager Features
Tests for requirements 5-8: Spread cost tracking, queue awareness,
adaptive slippage, and enhanced rejection logic.
"""

import unittest
from datetime import datetime, time
from bid_ask_manager import (
    BidAskManager, BidAskQuote, TradeExecution, SpreadCostTracker,
    QueuePositionMonitor, OrderRejectionValidator, AdaptiveSlippageModel,
    SpreadAnalyzer
)


class TestTradeExecution(unittest.TestCase):
    """Test TradeExecution data class."""
    
    def test_passive_execution_spread_saved(self):
        """Test that passive executions record spread saved."""
        execution = TradeExecution(
            symbol="ES",
            side="long",
            signal_price=4500.00,
            spread_at_order=0.25,
            fill_price=4500.00,
            quantity=1,
            order_type="passive",
            timestamp=datetime.now()
        )
        
        self.assertEqual(execution.spread_saved, 0.25)
    
    def test_aggressive_execution_spread_paid(self):
        """Test that aggressive executions record spread paid."""
        execution = TradeExecution(
            symbol="ES",
            side="long",
            signal_price=4500.00,
            spread_at_order=0.25,
            fill_price=4500.25,
            quantity=1,
            order_type="aggressive",
            timestamp=datetime.now()
        )
        
        self.assertEqual(execution.spread_saved, -0.25)


class TestSpreadCostTracker(unittest.TestCase):
    """Test SpreadCostTracker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = SpreadCostTracker()
    
    def test_initial_state(self):
        """Test initial tracker state."""
        stats = self.tracker.get_statistics()
        self.assertEqual(stats['total_trades'], 0)
        self.assertEqual(stats['passive_fill_rate'], 0.0)
    
    def test_record_passive_execution(self):
        """Test recording passive execution."""
        execution = TradeExecution(
            symbol="ES",
            side="long",
            signal_price=4500.00,
            spread_at_order=0.25,
            fill_price=4500.00,
            quantity=2,
            order_type="passive",
            timestamp=datetime.now()
        )
        
        self.tracker.record_execution(execution)
        
        stats = self.tracker.get_statistics()
        self.assertEqual(stats['total_trades'], 1)
        self.assertEqual(stats['passive_fills'], 1)
        self.assertEqual(stats['total_spread_saved'], 0.5)  # 0.25 * 2 contracts
    
    def test_passive_fill_rate(self):
        """Test passive fill rate calculation."""
        # Record 3 passive, 1 aggressive
        for i in range(3):
            execution = TradeExecution(
                symbol="ES",
                side="long",
                signal_price=4500.00,
                spread_at_order=0.25,
                fill_price=4500.00,
                quantity=1,
                order_type="passive",
                timestamp=datetime.now()
            )
            self.tracker.record_execution(execution)
        
        execution = TradeExecution(
            symbol="ES",
            side="long",
            signal_price=4500.00,
            spread_at_order=0.25,
            fill_price=4500.25,
            quantity=1,
            order_type="aggressive",
            timestamp=datetime.now()
        )
        self.tracker.record_execution(execution)
        
        stats = self.tracker.get_statistics()
        self.assertEqual(stats['total_trades'], 4)
        self.assertEqual(stats['passive_fill_rate'], 0.75)  # 3/4


class TestQueuePositionMonitor(unittest.TestCase):
    """Test queue position monitoring."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "max_queue_size": 100,
            "queue_jump_threshold": 50,
            "passive_order_timeout": 10
        }
        self.monitor = QueuePositionMonitor(self.config)
    
    def test_no_jump_when_at_front(self):
        """Test no queue jump when already at front."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        should_jump, new_price, reason = self.monitor.should_jump_queue(quote, "long", 0)
        
        self.assertFalse(should_jump)
        self.assertIn("front", reason.lower())
    
    def test_jump_when_queue_large(self):
        """Test queue jump when position is far back."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        should_jump, new_price, reason = self.monitor.should_jump_queue(quote, "long", 60)
        
        self.assertTrue(should_jump)
        self.assertEqual(new_price, 4500.25)  # bid + 1 tick
        self.assertIn("jumping", reason.lower())
    
    def test_cancel_on_timeout(self):
        """Test order cancellation on timeout."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        should_cancel, reason = self.monitor.should_cancel_and_reroute(quote, "long", 50, 15)
        
        self.assertTrue(should_cancel)
        self.assertIn("timeout", reason.lower())


class TestOrderRejectionValidator(unittest.TestCase):
    """Test enhanced order rejection logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "max_acceptable_spread": 1.0,
            "min_bid_ask_size": 5
        }
        self.validator = OrderRejectionValidator(self.config)
    
    def test_reject_inverted_spread(self):
        """Test rejection of inverted spread."""
        quote = BidAskQuote(
            bid_price=4500.25,  # Higher than ask - data error
            ask_price=4500.00,
            bid_size=10,
            ask_size=10,
            last_trade_price=4500.00,
            timestamp=1000000
        )
        
        analyzer = SpreadAnalyzer()
        is_valid, reason = self.validator.validate_order_entry(quote, analyzer)
        
        self.assertFalse(is_valid)
        self.assertIn("inverted", reason.lower())
    
    def test_reject_thin_liquidity(self):
        """Test rejection when liquidity too thin."""
        quote = BidAskQuote(
            bid_price=4500.00,
            ask_price=4500.25,
            bid_size=2,  # Below minimum
            ask_size=10,
            last_trade_price=4500.25,
            timestamp=1000000
        )
        
        analyzer = SpreadAnalyzer()
        is_valid, reason = self.validator.validate_order_entry(quote, analyzer)
        
        self.assertFalse(is_valid)
        self.assertIn("liquidity", reason.lower())
    
    def test_reject_widening_spread(self):
        """Test rejection when spread is widening."""
        analyzer = SpreadAnalyzer()
        
        # Create widening spread pattern
        for spread in [0.25, 0.30, 0.35, 0.40, 0.45]:
            analyzer.update(spread)
        
        quote = BidAskQuote(4500.00, 4500.50, 10, 10, 4500.25, 1000000)
        is_valid, reason = self.validator.validate_order_entry(quote, analyzer)
        
        self.assertFalse(is_valid)
        self.assertIn("stress", reason.lower())


class TestAdaptiveSlippageModel(unittest.TestCase):
    """Test adaptive slippage model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "normal_hours_slippage_ticks": 1.0,
            "illiquid_hours_slippage_ticks": 2.0,
            "max_slippage_ticks": 3.0,
            "illiquid_hours_start": time(0, 0),
            "illiquid_hours_end": time(9, 30),
            "timezone": "America/New_York"
        }
        self.model = AdaptiveSlippageModel(self.config)
    
    def test_normal_hours_slippage(self):
        """Test slippage during normal hours."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        analyzer = SpreadAnalyzer()
        
        # Build baseline
        for _ in range(30):
            analyzer.update(0.25)
        
        # Normal trading hours (10 AM)
        timestamp = datetime(2024, 1, 1, 10, 0)
        slippage = self.model.calculate_expected_slippage(quote, timestamp, analyzer)
        
        self.assertEqual(slippage, 1.0)
    
    def test_illiquid_hours_slippage(self):
        """Test increased slippage during illiquid hours."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        analyzer = SpreadAnalyzer()
        
        for _ in range(30):
            analyzer.update(0.25)
        
        # Early morning (2 AM)
        timestamp = datetime(2024, 1, 1, 2, 0)
        slippage = self.model.calculate_expected_slippage(quote, timestamp, analyzer)
        
        self.assertEqual(slippage, 2.0)
    
    def test_avoid_trading_wide_spread(self):
        """Test recommendation to avoid trading when spread abnormally wide."""
        quote = BidAskQuote(4500.00, 4501.00, 10, 10, 4500.50, 1000000)  # Very wide
        analyzer = SpreadAnalyzer()
        
        # Build baseline with normal spreads
        timestamp_base = datetime(2024, 1, 1, 10, 0)
        for i in range(30):
            analyzer.update(0.25, timestamp_base)
        
        # Check if should avoid
        should_avoid, reason = self.model.should_avoid_trading(quote, timestamp_base, analyzer)
        
        self.assertTrue(should_avoid)
        self.assertIn("normal", reason.lower())


class TestSpreadAnalyzerEnhancements(unittest.TestCase):
    """Test enhanced spread analyzer features."""
    
    def test_time_of_day_tracking(self):
        """Test time-of-day spread pattern tracking."""
        analyzer = SpreadAnalyzer()
        
        # Add spreads for 10 AM hour
        timestamp_10am = datetime(2024, 1, 1, 10, 30)
        for i in range(10):
            analyzer.update(0.25, timestamp_10am)
        
        # Add spreads for 2 AM hour (wider spreads typically)
        timestamp_2am = datetime(2024, 1, 1, 2, 30)
        for i in range(10):
            analyzer.update(0.50, timestamp_2am)
        
        # Check expected spread for each hour
        expected_10am = analyzer.get_expected_spread_for_time(timestamp_10am)
        expected_2am = analyzer.get_expected_spread_for_time(timestamp_2am)
        
        self.assertAlmostEqual(expected_10am, 0.25, places=2)
        self.assertAlmostEqual(expected_2am, 0.50, places=2)
    
    def test_spread_widening_detection(self):
        """Test detection of rapidly widening spreads."""
        analyzer = SpreadAnalyzer()
        
        # Create widening pattern
        for spread in [0.25, 0.30, 0.35, 0.40]:
            analyzer.update(spread)
        
        is_widening, reason = analyzer.is_spread_widening()
        
        self.assertTrue(is_widening)
        self.assertIn("widening", reason.lower())


class TestBidAskManagerEnhancements(unittest.TestCase):
    """Test enhanced BidAskManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "passive_order_timeout": 10,
            "spread_lookback_periods": 100,
            "abnormal_spread_multiplier": 2.0,
            "high_volatility_spread_mult": 3.0,
            "calm_market_spread_mult": 1.5,
            "use_mixed_order_strategy": False,
            "max_queue_size": 100,
            "queue_jump_threshold": 50,
            "min_bid_ask_size": 1,
            "max_acceptable_spread": None,
            "normal_hours_slippage_ticks": 1.0,
            "illiquid_hours_slippage_ticks": 2.0,
            "max_slippage_ticks": 3.0,
            "timezone": "America/New_York"
        }
        self.manager = BidAskManager(self.config)
    
    def test_record_trade_execution(self):
        """Test recording trade execution."""
        # Add quote first
        self.manager.update_quote("ES", 4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        # Record execution
        self.manager.record_trade_execution(
            symbol="ES",
            side="long",
            signal_price=4500.00,
            fill_price=4500.00,
            quantity=1,
            order_type="passive"
        )
        
        stats = self.manager.get_spread_cost_stats()
        self.assertEqual(stats['total_trades'], 1)
        self.assertEqual(stats['passive_fills'], 1)
    
    def test_enhanced_validation(self):
        """Test enhanced entry validation."""
        # Add invalid quote (inverted spread)
        self.manager.update_quote("ES", 4500.25, 4500.00, 10, 10, 4500.00, 1000000)
        
        is_valid, reason = self.manager.validate_entry_spread("ES")
        
        self.assertFalse(is_valid)
        self.assertIn("inverted", reason.lower())
    
    def test_expected_slippage(self):
        """Test expected slippage calculation."""
        # Build baseline
        for i in range(30):
            self.manager.update_quote("ES", 4500.00, 4500.25, 10, 10, 4500.25, 1000000 + i)
        
        timestamp = datetime(2024, 1, 1, 10, 0)
        slippage = self.manager.get_expected_slippage("ES", timestamp)
        
        self.assertIsNotNone(slippage)
        self.assertGreater(slippage, 0)


if __name__ == '__main__':
    unittest.main()
