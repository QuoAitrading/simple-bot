# Backtesting and Monitoring Guide

## Overview

The VWAP Bounce Bot now includes a comprehensive backtesting framework and enhanced monitoring capabilities. This guide covers how to use these features.

## Backtesting Framework

### Components

1. **Historical Data Loader** - Loads tick and bar data from CSV files
2. **Order Fill Simulator** - Simulates realistic order fills with slippage
3. **Performance Metrics** - Calculates comprehensive trading statistics
4. **Report Generator** - Creates detailed performance reports

### Quick Start

Generate sample data (for testing):
```bash
python generate_sample_data.py
```

Run a basic backtest:
```bash
python main.py --mode backtest --days 7
```

### Data Format

The backtesting engine expects CSV files in `./historical_data/`:

**Tick Data** (`{SYMBOL}_ticks.csv`):
```
timestamp,price,volume
2024-01-15T09:30:00,4500.00,5
2024-01-15T09:30:10,4500.25,3
```

**Bar Data** (`{SYMBOL}_1min.csv` or `{SYMBOL}_15min.csv`):
```
timestamp,open,high,low,close,volume
2024-01-15T09:30:00,4500.00,4501.00,4499.50,4500.50,100
```

### Performance Metrics

The backtesting engine calculates:

- **Total P&L**: Net profit/loss
- **Win Rate**: Percentage of winning trades
- **Average Win/Loss**: Mean profit and loss per trade
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted returns (annualized)
- **Profit Factor**: Gross profit / gross loss
- **Time in Market**: Percentage of time with active positions

### Order Simulation

The simulator handles three order types:

1. **Market Orders**
   - Fill at next bar's open price
   - Add slippage (default: 0.5 ticks)

2. **Stop Orders**
   - Trigger when bar high/low crosses stop price
   - Fill at stop price + slippage

3. **Limit Orders**
   - Fill when price reaches limit
   - Best-case execution (no slippage)

### Example: Custom Date Range

```bash
python main.py --mode backtest \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --initial-equity 50000 \
  --report january_backtest.txt
```

### Example: Multiple Symbols

Currently supports one symbol at a time. To test multiple symbols:

```bash
python main.py --mode backtest --symbol MES --days 30
python main.py --mode backtest --symbol MNQ --days 30
```

## Enhanced Logging

### Structured JSON Logs

Logs are written in JSON format to `./logs/vwap_bot.log`:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "logger": "vwap_bot",
  "message": "Trade executed",
  "module": "vwap_bounce_bot",
  "function": "execute_entry",
  "line": 1058,
  "extra": {
    "event_type": "trade_execution",
    "side": "long",
    "quantity": 1,
    "entry_price": 4500.25
  }
}
```

### Log Levels

- **DEBUG**: Internal calculations, detailed state
- **INFO**: Normal operations, trades, signals
- **WARNING**: Unusual conditions, approaching limits
- **ERROR**: Failures requiring attention
- **CRITICAL**: Emergency stops, system threats

### Sensitive Data Protection

The logging system automatically redacts sensitive information:

- API tokens
- API keys
- Passwords
- Secrets
- Authorization headers

Example:
```
Before: "API Token: abc123secret"
After:  "API Token: ***"
```

### Log Rotation

Logs automatically rotate daily and are kept for 30 days:

- `vwap_bot.log` - Current day
- `vwap_bot.log.2024-01-14` - Previous day
- Compressed after 7 days (optional)
- Deleted after 30 days

### Audit Trail

Specialized audit logs track all important decisions:

```bash
# View audit log
tail -f ./logs/audit.log
```

Audit log includes:
- Trade executions with full context
- Signal evaluations (accepted/rejected)
- Position changes
- Risk limit checks
- Parameter changes

## Health Monitoring

### Health Check Endpoint

When running in live mode, an HTTP server provides health status:

```bash
# Start bot
python main.py --mode live --dry-run

# Check health (in another terminal)
curl http://localhost:8080/health
```

Response:
```json
{
  "healthy": true,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "checks": {
    "bot_status": true,
    "broker_connection": true,
    "data_feed": true
  },
  "messages": ["All systems operational"]
}
```

### Unhealthy Response

When issues are detected:

```json
{
  "healthy": false,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "checks": {
    "bot_status": true,
    "broker_connection": false,
    "data_feed": true
  },
  "messages": ["No data for 120 seconds"]
}
```

HTTP status codes:
- `200 OK` - All checks passed
- `503 Service Unavailable` - One or more checks failed

### Custom Health Checks

You can add custom health checks:

```python
from monitoring import HealthChecker

def check_disk_space():
    import shutil
    stat = shutil.disk_usage('.')
    free_gb = stat.free / (1024**3)
    if free_gb < 1.0:
        return False, f"Low disk space: {free_gb:.2f}GB"
    return True, "Disk space OK"

health_checker.add_custom_check(check_disk_space)
```

## Metrics Collection

### Performance Metrics

The bot tracks:

- **API Call Latency**: Average response time for broker API calls
- **Event Loop Time**: Time per iteration of the event loop
- **Order Execution Time**: Time from order placement to fill
- **Data Feed Lag**: Delay in receiving market data

### Accessing Metrics

```python
from monitoring import MetricsCollector

collector = MetricsCollector()

# Record API call
collector.record_api_call(latency_ms=45.2, success=True)

# Get current metrics
metrics = collector.get_metrics()
print(metrics['api_call_latency_ms'])  # 45.2
```

## Alerting System

### Built-in Alerts

The system monitors:

- Daily loss limit approaching (80% threshold)
- Max drawdown exceeded
- API connection lost
- Data feed lag (>5 seconds)
- High order rejection rate

### Alert Handlers

Configure alert delivery:

```python
from monitoring import AlertManager

def email_handler(alert):
    # Send email notification
    pass

def sms_handler(alert):
    # Send SMS for critical alerts
    if alert.level == 'critical':
        # Send SMS
        pass

alert_manager = AlertManager(config)
alert_manager.add_handler(email_handler)
alert_manager.add_handler(sms_handler)
```

### Manual Alerts

Send custom alerts:

```python
alert_manager.send_alert(
    level='warning',
    title='Custom Alert',
    message='Something noteworthy happened'
)
```

## Configuration

### Environment Variables

```bash
# Required for live trading
export TOPSTEP_API_TOKEN='your_token_here'
export CONFIRM_LIVE_TRADING=1  # Safety confirmation

# Optional
export BOT_ENVIRONMENT='production'
export BOT_MAX_TRADES_PER_DAY=5
export BOT_DAILY_LOSS_LIMIT=200
```

### Command-Line Options

```bash
# Set log level
python main.py --mode live --dry-run --log-level DEBUG

# Custom health check port
python main.py --mode live --health-check-port 9000

# Disable health check server
python main.py --mode live --no-health-check
```

## Best Practices

### Backtesting

1. **Use realistic data** - Include market gaps, holidays, low liquidity periods
2. **Validate data quality** - Check for gaps and invalid prices
3. **Account for slippage** - Default 0.5 ticks, adjust based on your instrument
4. **Include commissions** - Default $2.50 per contract round-trip
5. **Test multiple scenarios** - Trending, ranging, volatile markets
6. **Walk-forward analysis** - Test on different time periods

### Logging

1. **Use appropriate log levels** - Don't log everything at INFO
2. **Include context** - Add correlation IDs for trade lifecycle
3. **Monitor log file size** - Rotation prevents disk issues
4. **Review logs regularly** - Look for WARNING and ERROR messages
5. **Protect sensitive data** - Never log API tokens or passwords

### Monitoring

1. **Set up health checks** - Use in production deployments
2. **Monitor key metrics** - API latency, event loop performance
3. **Configure alerts** - Email for warnings, SMS for critical
4. **Regular testing** - Test alert delivery monthly
5. **Dashboard integration** - Feed metrics to Grafana or similar

## Troubleshooting

### Backtest shows zero trades

- Check data files exist in `./historical_data/`
- Verify date range overlaps with available data
- Check that strategy logic is integrated (placeholder by default)

### Health check returns 503

- Check bot_status for emergency stops
- Verify broker connection is active
- Ensure data feed is receiving ticks

### Logs missing sensitive data redaction

- Verify SensitiveDataFilter is added to handlers
- Check pattern matches in filter configuration
- Test with sample log messages

### High API latency

- Check network connectivity
- Verify broker API is responding normally
- Consider increasing timeout thresholds

## Examples

See `example_usage.py` for complete examples:

```bash
python example_usage.py
```

## Further Reading

- [Original README](README.md) - Bot overview and trading strategy
- [Configuration Guide](config.py) - All configuration options
- [Test Suite](test_backtest_monitoring.py) - Example usage of components
