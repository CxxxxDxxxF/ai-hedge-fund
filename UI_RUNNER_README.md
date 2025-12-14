# Terminal UI Runner for Deterministic Backtest

## Quick Start

### 1. Install Dependencies

`rich` is already installed (it was in the project dependencies).

If you need to install it manually:
```bash
poetry add rich
```

### 2. Run the UI

```bash
poetry run python run_backtest_ui.py
```

Or with explicit deterministic mode:
```bash
HEDGEFUND_NO_LLM=1 poetry run python run_backtest_ui.py
```

## What You'll See

The UI shows a live-updating panel that displays:

- **Day**: Current day number / Total days
- **Date**: Current trading date
- **Portfolio**: Current portfolio value
- **Agents**: Number of agents that processed
- **Trades Today**: Number of trades executed today
- **Status**: Current status (PROCESSING, COMPLETE, ERROR, etc.)

The panel updates in real-time as each trading day is processed.

## Example Output

```
╭─────────────────────── Deterministic Backtest Runner ────────────────────────╮
│ Day:        3 / 7                                                            │
│ Date:       2024-01-04                                                       │
│ Portfolio:  $100,123.45                                                       │
│ Agents:     5                                                                │
│ Trades Today: 2                                                               │
│ Status:     COMPLETE                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Notes

- The invariant logs (e.g., `[   0] 2024-01-02 | PV=$100,000 | Agents=5 | Δt=0.44s`) will still print to stderr - this is expected behavior for observability
- The UI panel updates every 0.5 seconds per day
- If an error occurs, it will be displayed in the panel
- The backtest completes with a summary showing initial/final values and total return

## Customization

You can modify the date range and tickers in `run_backtest_ui.py`:

```python
start_date = "2024-01-02"
end_date = "2024-01-10"
tickers = ["AAPL"]
```

## Troubleshooting

If you see import errors:
```bash
PYTHONPATH=. poetry run python run_backtest_ui.py
```

If the UI doesn't update:
- Make sure your terminal supports ANSI escape codes
- Try running in a different terminal (not all terminals support `rich` Live updates)
