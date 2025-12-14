# Health Monitoring System

## Overview

The Health Monitoring System tracks portfolio health in real-time during backtests, providing alerts and warnings when health degrades.

## What Gets Monitored

### 1. **Capital Health**
- NAV (Net Asset Value) as % of initial capital
- Cash ratio (cash / NAV)
- Margin usage (margin used / NAV)

**Thresholds:**
- Critical: NAV < 30% of initial, Cash < 5% of NAV
- Warning: NAV < 50% of initial, Cash < 10% of NAV
- Caution: NAV < 70% of initial

### 2. **Exposure Health**
- Gross exposure (% of NAV)
- Net exposure (% of NAV)
- Maximum position size (% of NAV)
- Concentration risk (HHI-like measure)

**Thresholds:**
- Critical: Gross exposure > 200% of NAV, Single position > 30% of NAV
- Warning: Gross exposure > 150% of NAV, Single position > 25% of NAV

### 3. **Risk Health**
- Current drawdown from peak
- Daily return volatility
- Large daily losses

**Thresholds:**
- Critical: Drawdown > 20%
- Warning: Drawdown > 10%, Daily loss > 5%

### 4. **Constraint Compliance**
- Checks if portfolio violates capital constraints
- Tracks constraint violations

## Health Status Levels

1. **EXCELLENT** - Optimal conditions (score ≥ 0.9)
2. **HEALTHY** - All systems normal
3. **CAUTION** - Monitor closely
4. **WARNING** - Attention needed
5. **CRITICAL** - Immediate action required

## Health Score

Overall health score (0.0-1.0) calculated as weighted average:
- Capital Health: 30%
- Exposure Health: 25%
- Risk Health: 25%
- Constraint Compliance: 20%

## Integration

Health monitoring is automatically integrated into `deterministic_backtest.py`:

1. **Daily Health Checks** - Runs after each trading day
2. **Health Warnings** - Logged to stderr when health degrades
3. **Health Summary** - Included in backtest summary output
4. **Health History** - Stored in metrics for analysis

## Example Output

```
================================================================================
PORTFOLIO HEALTH SUMMARY
================================================================================
Overall Health Score: 0.85/1.00
Overall Status: HEALTHY
NAV: $105,234.56 (105.2% of initial)
Active Alerts: 0

Health Checks:
  ✅ capital_health: HEALTHY (score: 0.95)
  ✅ exposure_health: HEALTHY (score: 0.90)
  ⚠️ risk_health: CAUTION (score: 0.75)
  ✅ constraint_compliance: HEALTHY (score: 1.00)
================================================================================
```

## Health Alerts

When health degrades, alerts are generated:

- **Critical Alerts**: NAV critically low, gross exposure critical, drawdown critical
- **Warning Alerts**: NAV low, cash low, high concentration

Alerts are logged to stderr during backtest execution:

```
HEALTH WARNING: Score 0.65, NAV 45.2%, Alerts: 2
```

## Health History

Health metrics are stored in `metrics["health_history"]` with:
- Date
- Overall score
- Overall status
- NAV and NAV %
- Number of active alerts

## Usage

Health monitoring is automatic - no configuration needed. Just run backtests as usual:

```bash
python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

Health checks run automatically and results are included in the summary.

## Health Snapshots

If `--snapshot-dir` is provided, health snapshots are saved to `snapshot_dir/health/`:
- `health_YYYYMMDD_HHMMSS.json` - Individual health snapshots

## API Usage

You can also use the health monitor programmatically:

```python
from src.health.health_monitor import HealthMonitor

monitor = HealthMonitor(initial_capital=100000.0)

health_metrics = monitor.calculate_overall_health(
    nav=105000.0,
    cash=5000.0,
    margin_used=0.0,
    gross_exposure=95000.0,
    net_exposure=90000.0,
    positions={...},
    prices={...},
)

print(f"Health Score: {health_metrics.overall_score:.2f}")
print(f"Status: {health_metrics.overall_status.value}")
print(f"Alerts: {len(health_metrics.active_alerts)}")
```

## Benefits

1. **Early Warning System** - Detects health issues before they become critical
2. **Risk Monitoring** - Tracks exposure and concentration risks
3. **Constraint Compliance** - Ensures portfolio stays within limits
4. **Performance Tracking** - Monitors drawdowns and returns
5. **Actionable Alerts** - Provides specific warnings when action is needed

## Future Enhancements

- Real-time health monitoring in live trading
- Health-based position sizing
- Health-based risk limits
- Health trend analysis
- Agent health awareness (agents can check health before trading)
