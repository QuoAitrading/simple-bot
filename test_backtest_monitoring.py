"""
Test backtesting framework and monitoring enhancements
"""

import unittest
import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtesting import (
    BacktestConfig, HistoricalDataLoader, OrderFillSimulator,
    PerformanceMetrics, BacktestEngine, ReportGenerator, Trade
)
from monitoring import (
    setup_logging, HealthChecker, HealthCheckStatus,
    MetricsCollector, AuditLogger,
    StructuredFormatter, SensitiveDataFilter
)


class TestHistoricalDataLoader(unittest.TestCase):
    """Test historical data loading"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
            data_path=self.temp_dir
        )
        self.loader = HistoricalDataLoader(self.config)
        
    def tearDown(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir)
        
    def test_load_bar_data_empty(self):
        """Test loading bar data when file doesn't exist"""
        bars = self.loader.load_bar_data("MES", "1min")
        self.assertEqual(len(bars), 0)
        
    def test_validate_data_quality_empty(self):
        """Test data quality validation with empty data"""
        is_valid, issues = self.loader.validate_data_quality([])
        self.assertFalse(is_valid)
        self.assertIn("No data available", issues)
        
    def test_validate_data_quality_invalid_price(self):
        """Test data quality validation with invalid price"""
        data = [
            {'timestamp': datetime.now(), 'price': -100, 'volume': 10},
        ]
        is_valid, issues = self.loader.validate_data_quality(data)
        self.assertFalse(is_valid)
        self.assertTrue(any('Invalid price' in issue for issue in issues))


class TestOrderFillSimulator(unittest.TestCase):
    """Test order fill simulation"""
    
    def setUp(self):
        """Setup test environment"""
        self.simulator = OrderFillSimulator(
            tick_size=0.25,
            tick_value=1.25,
            slippage_ticks=0.5
        )
        
    def test_market_order_buy(self):
        """Test market order buy simulation"""
        next_bar = {'open': 4500.0, 'high': 4501.0, 'low': 4499.0, 'close': 4500.5}
        fill_price = self.simulator.simulate_market_order('BUY', 4500.0, next_bar)
        
        # Should fill at open + slippage
        expected = 4500.0 + (0.5 * 0.25)
        self.assertEqual(fill_price, expected)
        
    def test_market_order_sell(self):
        """Test market order sell simulation"""
        next_bar = {'open': 4500.0, 'high': 4501.0, 'low': 4499.0, 'close': 4500.5}
        fill_price = self.simulator.simulate_market_order('SELL', 4500.0, next_bar)
        
        # Should fill at open - slippage
        expected = 4500.0 - (0.5 * 0.25)
        self.assertEqual(fill_price, expected)
        
    def test_stop_order_triggered(self):
        """Test stop order that gets triggered"""
        bar = {'high': 4510.0, 'low': 4500.0}
        fill_price = self.simulator.simulate_stop_order('BUY', 4505.0, bar)
        
        # Should trigger and fill with slippage
        self.assertIsNotNone(fill_price)
        self.assertGreater(fill_price, 4505.0)
        
    def test_stop_order_not_triggered(self):
        """Test stop order that doesn't trigger"""
        bar = {'high': 4504.0, 'low': 4500.0}
        fill_price = self.simulator.simulate_stop_order('BUY', 4505.0, bar)
        
        # Should not trigger
        self.assertIsNone(fill_price)
        
    def test_limit_order_filled(self):
        """Test limit order that fills"""
        bar = {'high': 4510.0, 'low': 4500.0}
        fill_price = self.simulator.simulate_limit_order('BUY', 4505.0, bar)
        
        # Should fill at limit price
        self.assertEqual(fill_price, 4505.0)
        
    def test_limit_order_not_filled(self):
        """Test limit order that doesn't fill"""
        bar = {'high': 4504.0, 'low': 4502.0}
        fill_price = self.simulator.simulate_limit_order('BUY', 4500.0, bar)
        
        # Should not fill (price didn't reach limit)
        self.assertIsNone(fill_price)


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics calculations"""
    
    def setUp(self):
        """Setup test environment"""
        self.metrics = PerformanceMetrics(
            initial_equity=25000.0,
            tick_value=1.25,
            commission_per_contract=2.50
        )
        
    def test_initial_state(self):
        """Test initial metrics state"""
        summary = self.metrics.get_summary()
        self.assertEqual(summary['total_trades'], 0)
        self.assertEqual(summary['total_pnl'], 0.0)
        self.assertEqual(summary['final_equity'], 25000.0)
        
    def test_add_winning_trade(self):
        """Test adding a winning trade"""
        trade = Trade(
            entry_time=datetime.now(),
            exit_time=datetime.now() + timedelta(minutes=10),
            symbol="MES",
            side="long",
            quantity=1,
            entry_price=4500.0,
            exit_price=4502.0,
            stop_price=4498.0,
            target_price=4503.0,
            exit_reason="target_reached",
            pnl=10.0,
            ticks=8.0,
            duration_minutes=10.0
        )
        
        self.metrics.add_trade(trade)
        summary = self.metrics.get_summary()
        
        self.assertEqual(summary['total_trades'], 1)
        self.assertEqual(summary['total_pnl'], 10.0)
        self.assertEqual(summary['win_rate'], 100.0)
        
    def test_calculate_win_rate(self):
        """Test win rate calculation"""
        # Add 3 winning trades
        for i in range(3):
            trade = Trade(
                entry_time=datetime.now(),
                exit_time=datetime.now() + timedelta(minutes=10),
                symbol="MES",
                side="long",
                quantity=1,
                entry_price=4500.0,
                exit_price=4502.0,
                stop_price=4498.0,
                target_price=4503.0,
                exit_reason="target_reached",
                pnl=10.0,
                ticks=8.0,
                duration_minutes=10.0
            )
            self.metrics.add_trade(trade)
            
        # Add 1 losing trade
        trade = Trade(
            entry_time=datetime.now(),
            exit_time=datetime.now() + timedelta(minutes=5),
            symbol="MES",
            side="long",
            quantity=1,
            entry_price=4500.0,
            exit_price=4498.0,
            stop_price=4498.0,
            target_price=4503.0,
            exit_reason="stop_loss",
            pnl=-5.0,
            ticks=-8.0,
            duration_minutes=5.0
        )
        self.metrics.add_trade(trade)
        
        summary = self.metrics.get_summary()
        self.assertEqual(summary['win_rate'], 75.0)  # 3 out of 4
        
    def test_calculate_average_win_loss(self):
        """Test average win/loss calculation"""
        # Add wins
        for _ in range(2):
            trade = Trade(
                entry_time=datetime.now(),
                exit_time=datetime.now() + timedelta(minutes=10),
                symbol="MES",
                side="long",
                quantity=1,
                entry_price=4500.0,
                exit_price=4502.0,
                stop_price=4498.0,
                target_price=4503.0,
                exit_reason="target_reached",
                pnl=10.0,
                ticks=8.0,
                duration_minutes=10.0
            )
            self.metrics.add_trade(trade)
            
        # Add loss
        trade = Trade(
            entry_time=datetime.now(),
            exit_time=datetime.now() + timedelta(minutes=5),
            symbol="MES",
            side="long",
            quantity=1,
            entry_price=4500.0,
            exit_price=4498.0,
            stop_price=4498.0,
            target_price=4503.0,
            exit_reason="stop_loss",
            pnl=-5.0,
            ticks=-8.0,
            duration_minutes=5.0
        )
        self.metrics.add_trade(trade)
        
        avg_win, avg_loss = self.metrics.calculate_average_win_loss()
        self.assertEqual(avg_win, 10.0)
        self.assertEqual(avg_loss, -5.0)
        
    def test_calculate_profit_factor(self):
        """Test profit factor calculation"""
        # Add wins
        for _ in range(2):
            trade = Trade(
                entry_time=datetime.now(),
                exit_time=datetime.now() + timedelta(minutes=10),
                symbol="MES",
                side="long",
                quantity=1,
                entry_price=4500.0,
                exit_price=4502.0,
                stop_price=4498.0,
                target_price=4503.0,
                exit_reason="target_reached",
                pnl=10.0,
                ticks=8.0,
                duration_minutes=10.0
            )
            self.metrics.add_trade(trade)
            
        # Add loss
        trade = Trade(
            entry_time=datetime.now(),
            exit_time=datetime.now() + timedelta(minutes=5),
            symbol="MES",
            side="long",
            quantity=1,
            entry_price=4500.0,
            exit_price=4498.0,
            stop_price=4498.0,
            target_price=4503.0,
            exit_reason="stop_loss",
            pnl=-5.0,
            ticks=-8.0,
            duration_minutes=5.0
        )
        self.metrics.add_trade(trade)
        
        pf = self.metrics.calculate_profit_factor()
        self.assertEqual(pf, 4.0)  # 20 profit / 5 loss


class TestHealthChecker(unittest.TestCase):
    """Test health checker functionality"""
    
    def setUp(self):
        """Setup test environment"""
        self.bot_status = {
            'trading_enabled': True,
            'emergency_stop': False,
            'last_tick_time': datetime.now()
        }
        self.config = {
            'tick_timeout_seconds': 60
        }
        self.checker = HealthChecker(self.bot_status, self.config)
        
    def test_healthy_status(self):
        """Test healthy bot status"""
        is_ok, msg = self.checker.check_bot_status()
        self.assertTrue(is_ok)
        
    def test_emergency_stop(self):
        """Test emergency stop detection"""
        self.bot_status['emergency_stop'] = True
        is_ok, msg = self.checker.check_bot_status()
        self.assertFalse(is_ok)
        self.assertIn("Emergency stop", msg)
        
    def test_trading_disabled(self):
        """Test trading disabled detection"""
        self.bot_status['trading_enabled'] = False
        self.bot_status['stop_reason'] = 'daily_loss_limit'
        is_ok, msg = self.checker.check_bot_status()
        self.assertFalse(is_ok)
        self.assertIn("Trading disabled", msg)
        
    def test_get_overall_status(self):
        """Test overall health status"""
        status = self.checker.get_status()
        self.assertIsInstance(status, HealthCheckStatus)
        self.assertTrue(status.healthy)
        self.assertIn('bot_status', status.checks)


class TestMetricsCollector(unittest.TestCase):
    """Test metrics collection"""
    
    def setUp(self):
        """Setup test environment"""
        self.collector = MetricsCollector()
        
    def test_record_api_call(self):
        """Test API call recording"""
        self.collector.record_api_call(50.0, True)
        metrics = self.collector.get_metrics()
        
        self.assertEqual(metrics['api_call_latency_ms'], 50.0)
        self.assertEqual(metrics['api_error_count'], 0)
        
    def test_record_api_error(self):
        """Test API error recording"""
        self.collector.record_api_call(100.0, False)
        metrics = self.collector.get_metrics()
        
        self.assertEqual(metrics['api_error_count'], 1)
        
    def test_record_event_loop_iteration(self):
        """Test event loop iteration recording"""
        self.collector.record_event_loop_iteration(10.0)
        metrics = self.collector.get_metrics()
        
        self.assertEqual(metrics['event_loop_iteration_time_ms'], 10.0)
        
    def test_update_position_metrics(self):
        """Test position metrics update"""
        self.collector.update_position_metrics(
            position_qty=1,
            daily_pnl=50.0,
            daily_trades=3
        )
        metrics = self.collector.get_metrics()
        
        self.assertEqual(metrics['current_position_qty'], 1)
        self.assertEqual(metrics['daily_pnl'], 50.0)
        self.assertEqual(metrics['total_trades_today'], 3)


class TestSensitiveDataFilter(unittest.TestCase):
    """Test sensitive data filtering"""
    
    def setUp(self):
        """Setup test environment"""
        self.filter = SensitiveDataFilter()
        
    def test_filter_api_token(self):
        """Test API token redaction"""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg="API Token: abc123secret",
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        # The filter modifies the message to replace the value
        self.assertIn('***', record.msg)
        self.assertNotIn('abc123secret', record.msg.lower())


class TestReportGenerator(unittest.TestCase):
    """Test report generation"""
    
    def setUp(self):
        """Setup test environment"""
        self.metrics = PerformanceMetrics(
            initial_equity=25000.0,
            tick_value=1.25,
            commission_per_contract=2.50
        )
        
        # Add sample trades
        for i in range(3):
            trade = Trade(
                entry_time=datetime.now() - timedelta(hours=i+1),
                exit_time=datetime.now() - timedelta(hours=i),
                symbol="MES",
                side="long" if i % 2 == 0 else "short",
                quantity=1,
                entry_price=4500.0,
                exit_price=4502.0 if i < 2 else 4498.0,
                stop_price=4498.0,
                target_price=4503.0,
                exit_reason="target_reached" if i < 2 else "stop_loss",
                pnl=10.0 if i < 2 else -5.0,
                ticks=8.0 if i < 2 else -8.0,
                duration_minutes=10.0
            )
            self.metrics.add_trade(trade)
            
        self.generator = ReportGenerator(self.metrics)
        
    def test_generate_trade_breakdown(self):
        """Test trade breakdown generation"""
        breakdown = self.generator.generate_trade_breakdown()
        
        self.assertIn("TRADE-BY-TRADE BREAKDOWN", breakdown)
        self.assertIn("Entry Time", breakdown)
        self.assertIn("P&L", breakdown)
        
    def test_generate_daily_pnl(self):
        """Test daily P&L generation"""
        daily_pnl = self.generator.generate_daily_pnl()
        
        self.assertIsInstance(daily_pnl, dict)
        # Should have entries for today
        self.assertGreater(len(daily_pnl), 0)


def run_tests():
    """Run all tests"""
    print("="*60)
    print("Running Backtesting and Monitoring Tests")
    print("="*60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestHistoricalDataLoader))
    suite.addTests(loader.loadTestsFromTestCase(TestOrderFillSimulator))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestMetricsCollector))
    suite.addTests(loader.loadTestsFromTestCase(TestSensitiveDataFilter))
    suite.addTests(loader.loadTestsFromTestCase(TestReportGenerator))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
