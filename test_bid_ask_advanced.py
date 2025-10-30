"""
Tests for Advanced Bid/Ask Manager Features (Requirements 9-15)
Tests for exit optimization, spread-aware sizing, market classification,
fill probability, and post-trade analysis.
"""

import unittest
from datetime import datetime
from bid_ask_manager import (
    BidAskManager, BidAskQuote, MarketConditionClassifier, FillProbabilityEstimator,
    PostTradeAnalyzer, SpreadAwarePositionSizer, ExitOrderOptimizer, SpreadAnalyzer
)


class TestMarketConditionClassifier(unittest.TestCase):
    """Test market condition classification."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tight_spread_multiplier": 1.2,
            "wide_spread_multiplier": 2.0,
            "extreme_spread_multiplier": 3.0,
            "low_volume_threshold": 0.5
        }
        self.classifier = MarketConditionClassifier(self.config)
    
    def test_normal_market(self):
        """Test classification of normal market."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        analyzer = SpreadAnalyzer()
        
        # Build baseline
        for _ in range(30):
            analyzer.update(0.25)
        
        condition, reason = self.classifier.classify_market(quote, analyzer)
        
        self.assertEqual(condition, "normal")
        self.assertIn("tight", reason.lower())
    
    def test_stressed_market(self):
        """Test classification of stressed market."""
        quote = BidAskQuote(4500.00, 4501.00, 5, 5, 4500.50, 1000000)  # Very wide
        analyzer = SpreadAnalyzer()
        
        # Build baseline with normal spreads
        for _ in range(30):
            analyzer.update(0.25)
        
        condition, reason = self.classifier.classify_market(quote, analyzer)
        
        self.assertEqual(condition, "stressed")
        self.assertIn("extreme", reason.lower())
    
    def test_illiquid_market(self):
        """Test classification of illiquid market."""
        quote = BidAskQuote(4500.00, 4500.60, 5, 5, 4500.30, 1000000)  # 2.4x spread + low size
        analyzer = SpreadAnalyzer()
        
        for _ in range(30):
            analyzer.update(0.25)
        
        condition, reason = self.classifier.classify_market(quote, analyzer)
        
        # Should be either illiquid or volatile depending on exact ratio
        self.assertIn(condition, ["illiquid", "volatile"])
        self.assertIn("spread", reason.lower())


class TestFillProbabilityEstimator(unittest.TestCase):
    """Test fill probability estimation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "passive_order_timeout": 10,
            "min_fill_probability": 0.5
        }
        self.estimator = FillProbabilityEstimator(self.config)
    
    def test_high_probability_fill(self):
        """Test high probability estimate."""
        quote = BidAskQuote(4500.00, 4500.25, 5, 20, 4500.25, 1000000)  # High ask size
        
        prob, wait, reason = self.estimator.estimate_fill_probability(quote, "long")
        
        self.assertGreater(prob, 0.7)
        self.assertLess(wait, 10.0)
    
    def test_low_probability_fill(self):
        """Test low probability estimate."""
        quote = BidAskQuote(4500.00, 4500.25, 20, 5, 4500.25, 1000000)  # High bid size
        
        prob, wait, reason = self.estimator.estimate_fill_probability(quote, "long")
        
        self.assertLess(prob, 0.7)
    
    def test_should_wait_decision(self):
        """Test decision to wait for passive fill."""
        should_wait, reason = self.estimator.should_wait_for_passive(0.8, 5.0)
        self.assertTrue(should_wait)
        
        should_wait, reason = self.estimator.should_wait_for_passive(0.3, 5.0)
        self.assertFalse(should_wait)
        self.assertIn("probability too low", reason.lower())


class TestPostTradeAnalyzer(unittest.TestCase):
    """Test post-trade analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = PostTradeAnalyzer()
    
    def test_record_trade(self):
        """Test recording trade execution."""
        self.analyzer.record_trade(
            signal_price=4500.00,
            fill_price=4500.00,
            side="long",
            order_type="passive",
            spread_at_order=0.25,
            fill_time_seconds=5.0,
            estimated_costs={"total": 0.50},
            actual_costs={"total": 0.25}
        )
        
        self.assertEqual(len(self.analyzer.trade_records), 1)
        self.assertEqual(self.analyzer.trade_records[0]["order_type"], "passive")
    
    def test_learning_insights(self):
        """Test learning insights generation."""
        # Record multiple trades
        for i in range(5):
            self.analyzer.record_trade(
                signal_price=4500.00,
                fill_price=4500.00,
                side="long",
                order_type="passive" if i < 3 else "aggressive",
                spread_at_order=0.25,
                fill_time_seconds=5.0 if i < 3 else 2.0,
                estimated_costs={"total": 0.50},
                actual_costs={"total": 0.25 if i < 3 else 0.75}
            )
        
        insights = self.analyzer.get_learning_insights("normal")
        
        self.assertEqual(insights["total_trades"], 5)
        self.assertEqual(insights["passive_count"], 3)
        self.assertEqual(insights["aggressive_count"], 2)


class TestSpreadAwarePositionSizer(unittest.TestCase):
    """Test spread-aware position sizing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "tick_value": 12.50,
            "max_transaction_cost_pct": 0.15
        }
        self.sizer = SpreadAwarePositionSizer(self.config)
    
    def test_normal_position_size(self):
        """Test position sizing with acceptable spread."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)  # 1 tick spread
        
        contracts, breakdown = self.sizer.calculate_position_size(
            quote=quote,
            base_contracts=2,
            expected_profit_ticks=20.0,  # Higher profit to make costs acceptable
            slippage_ticks=1.0,
            commission_per_contract=2.50
        )
        
        # With higher expected profit, should not reduce
        self.assertGreaterEqual(contracts, 1)  # At least 1
        self.assertIn("spread_ticks", breakdown)
    
    def test_reduced_position_size(self):
        """Test position size reduction with wide spread."""
        quote = BidAskQuote(4500.00, 4502.00, 10, 10, 4501.00, 1000000)  # 8 tick spread
        
        contracts, breakdown = self.sizer.calculate_position_size(
            quote=quote,
            base_contracts=5,
            expected_profit_ticks=10.0,
            slippage_ticks=1.0,
            commission_per_contract=2.50
        )
        
        self.assertLess(contracts, 5)  # Size reduced
        self.assertGreaterEqual(contracts, 1)  # At least 1


class TestExitOrderOptimizer(unittest.TestCase):
    """Test exit order optimization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "passive_order_timeout": 10
        }
        self.optimizer = ExitOrderOptimizer(self.config)
    
    def test_target_exit_passive(self):
        """Test profit target exit uses passive order."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        strategy = self.optimizer.get_exit_strategy("target", quote, "long")
        
        self.assertEqual(strategy["order_type"], "passive")
        self.assertEqual(strategy["limit_price"], quote.ask_price)  # Collect spread
        self.assertIn("collect spread", strategy["reason"].lower())
    
    def test_stop_exit_aggressive(self):
        """Test stop loss exit uses aggressive order."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        strategy = self.optimizer.get_exit_strategy("stop", quote, "long")
        
        self.assertEqual(strategy["order_type"], "aggressive")
        self.assertEqual(strategy["limit_price"], quote.bid_price)  # Fast exit
        self.assertIn("fast exit", strategy["reason"].lower())
    
    def test_time_flatten_aggressive(self):
        """Test time-based flatten uses aggressive order."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        strategy = self.optimizer.get_exit_strategy("time_flatten", quote, "long")
        
        self.assertEqual(strategy["order_type"], "aggressive")
        self.assertIn("before cutoff", strategy["reason"].lower())
    
    def test_partial_exit_passive_with_fallback(self):
        """Test partial exit tries passive with aggressive fallback."""
        quote = BidAskQuote(4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        strategy = self.optimizer.get_exit_strategy("partial", quote, "long")
        
        self.assertEqual(strategy["order_type"], "passive")
        self.assertIn("fallback_price", strategy)
        self.assertEqual(strategy["fallback_price"], quote.bid_price)


class TestBidAskManagerAdvanced(unittest.TestCase):
    """Test advanced BidAskManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "tick_size": 0.25,
            "tick_value": 12.50,
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
            "timezone": "America/New_York",
            "tight_spread_multiplier": 1.2,
            "wide_spread_multiplier": 2.0,
            "extreme_spread_multiplier": 3.0,
            "low_volume_threshold": 0.5,
            "min_fill_probability": 0.5,
            "max_transaction_cost_pct": 0.15,
            "commission_per_contract": 2.50
        }
        self.manager = BidAskManager(self.config)
    
    def test_market_classification(self):
        """Test market condition classification."""
        # Build baseline
        for i in range(30):
            self.manager.update_quote("ES", 4500.00, 4500.25, 10, 10, 4500.25, 1000000 + i)
        
        condition, reason = self.manager.classify_market_condition("ES")
        
        self.assertEqual(condition, "normal")
    
    def test_fill_probability_estimation(self):
        """Test fill probability estimation."""
        self.manager.update_quote("ES", 4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        prob, wait, reason = self.manager.estimate_fill_probability("ES", "long")
        
        self.assertGreater(prob, 0.0)
        self.assertGreater(wait, 0.0)
    
    def test_spread_aware_position_sizing(self):
        """Test spread-aware position sizing."""
        # Build baseline
        for i in range(30):
            self.manager.update_quote("ES", 4500.00, 4500.25, 10, 10, 4500.25, 1000000 + i)
        
        contracts, breakdown = self.manager.calculate_spread_aware_position_size(
            symbol="ES",
            base_contracts=2,
            expected_profit_ticks=10.0
        )
        
        self.assertGreaterEqual(contracts, 1)
        self.assertIn("spread_ticks", breakdown)
    
    def test_exit_order_strategy(self):
        """Test exit order strategy selection."""
        self.manager.update_quote("ES", 4500.00, 4500.25, 10, 10, 4500.25, 1000000)
        
        # Test target exit
        strategy = self.manager.get_exit_order_strategy("target", "ES", "long")
        self.assertEqual(strategy["order_type"], "passive")
        
        # Test stop exit
        strategy = self.manager.get_exit_order_strategy("stop", "ES", "long")
        self.assertEqual(strategy["order_type"], "aggressive")
    
    def test_post_trade_analysis_recording(self):
        """Test post-trade analysis recording."""
        self.manager.record_post_trade_analysis(
            signal_price=4500.00,
            fill_price=4500.00,
            side="long",
            order_type="passive",
            spread_at_order=0.25,
            fill_time_seconds=5.0,
            estimated_costs={"total": 0.50},
            actual_costs={"total": 0.25}
        )
        
        insights = self.manager.get_learning_insights("normal")
        self.assertEqual(insights["total_trades"], 1)


if __name__ == '__main__':
    unittest.main()
