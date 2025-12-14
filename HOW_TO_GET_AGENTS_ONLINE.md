# How to Get Your Agents Online and Training 🚀

Your "employees" (AI agents) are ready to work! Here's how to get them online and analyzing stocks.

## Quick Start Guide

### Step 1: Open Your Flow
1. Open the web UI at `http://localhost:5173`
2. You should see a flow canvas with a **"Portfolio Analyzer"** node
3. If you don't have a flow, create one from the left sidebar

### Step 2: Add Agents (Employees) to Your Flow

**Option A: From the Right Sidebar**
1. Click the **right sidebar toggle** (or press `⌘ + I`) to open the component panel
2. You'll see different categories:
   - **Analysts** - Your AI agents (Warren Buffett, Peter Lynch, etc.)
   - **Start Nodes** - Portfolio Input, Stock Input
   - **End Nodes** - Portfolio Manager
3. **Drag and drop** agents from the "Analysts" section onto your canvas
4. **Connect them** by dragging from the Portfolio Analyzer to each agent, then from agents to the Portfolio Manager

**Option B: Use the Left Sidebar**
1. The left sidebar shows your saved flows
2. You can also add components directly to the canvas

### Step 3: Configure Your Portfolio

1. **Click on the "Portfolio Analyzer" node** (the one with the pie chart icon)
2. Set your **Available Cash** (default: $100,000)
3. **Add Stock Positions**:
   - Click the **"+" button** to add a position
   - Enter:
     - **Ticker** (e.g., AAPL, MSFT, NVDA, TSLA, GOOGL)
     - **Quantity** (number of shares)
     - **Trade Price** (price per share)
   - Add multiple positions as needed

**Free Tickers (No API Key Required):**
- AAPL (Apple)
- GOOGL (Google)
- MSFT (Microsoft)
- NVDA (NVIDIA)
- TSLA (Tesla)

### Step 4: Configure Agent Models (Optional)

1. **Click on any agent node** (e.g., "Value Composite", "Growth Composite")
2. Select which **language model** each agent should use:
   - OpenAI models (GPT-4o, GPT-4o-mini)
   - Groq models (DeepSeek, Llama3)
   - Anthropic (Claude)
   - Or use the global model setting
3. Each agent can use a different model, or all can share one

### Step 5: Start Training! (Run the Hedge Fund)

You have two modes:

#### **Mode 1: Single Run (Live Analysis)**
1. In the Portfolio Analyzer node, make sure **"Single Run"** is selected
2. Click the **Play button (▶️)** on the Portfolio Analyzer node
3. Or press **`⌘ + Enter`** (Mac) / **`Ctrl + Enter`** (Windows)
4. Watch your agents go to work! You'll see:
   - Real-time status updates for each agent
   - Which ticker each agent is analyzing
   - Progress messages as they work
   - Final investment recommendations

#### **Mode 2: Backtest (Historical Training)**
1. In the Portfolio Analyzer node, switch to **"Backtest"** mode
2. Set your **Start Date** and **End Date**
3. Click the **Play button (▶️)**
4. The system will:
   - Run through each day in the date range
   - Show day-by-day portfolio performance
   - Calculate performance metrics (Sharpe ratio, drawdown, etc.)
   - Show you how your strategy would have performed historically

### Step 6: Monitor Your Agents

**In the Flow View:**
- **Color-coded nodes**: 
  - Gray = Idle
  - Yellow = Working (IN_PROGRESS)
  - Green = Complete
  - Red = Error
- **Click on any agent** to see their detailed analysis
- **Bottom panel** shows output and results

**In the Dashboard:**
1. Click the **Dashboard icon (📊)** in the top bar
2. See:
   - **Current Work Status**: What's running right now
   - **Active Strategies**: Which agents are working
   - **Agent Roster**: All your "employees" and their status
   - **Performance Metrics**: Results from backtests

### Step 7: View Results

**Agent Output:**
- Click on any agent node to see their analysis
- View their reasoning and recommendations

**Final Report:**
- Check the **"Investment Report"** node for final decisions
- Or view the **Portfolio Manager** node for aggregated signals

**Backtest Results:**
- View performance metrics in the dashboard
- See day-by-day results in the bottom panel
- Check Sharpe ratio, drawdown, and other metrics

## Tips for Success

### 1. **Start Simple**
- Begin with 2-3 agents
- Use free tickers (AAPL, MSFT, etc.)
- Run a single analysis first

### 2. **Build Your Team**
- Add more agents for diverse perspectives
- Mix value investors (Buffett) with growth investors (Lynch)
- Include technical analysts for different approaches

### 3. **Test Before Going Live**
- Run backtests to see historical performance
- Adjust your strategy based on results
- Try different date ranges

### 4. **Monitor Performance**
- Use the Dashboard to track agent activity
- Check performance metrics regularly
- Review agent recommendations

### 5. **Save Your Strategies**
- Save your flows for future use
- Create templates for common setups
- Duplicate successful flows

## Troubleshooting

### "No agents are working"
- Make sure you've added agents to your flow
- Connect them properly (Portfolio Analyzer → Agents → Portfolio Manager)
- Check that you have at least one API key configured

### "Agents stuck on IDLE"
- Verify your portfolio has tickers configured
- Make sure agents are connected to the Portfolio Analyzer
- Check the connection status in the dashboard

### "API errors"
- Go to Settings → API Keys
- Add at least one LLM API key (OpenAI, Groq, etc.)
- Make sure the key is valid and has credits

### "No results showing"
- Wait for agents to complete (can take 1-5 minutes)
- Check the bottom panel for output
- Look for error messages in agent nodes

## Example Workflow

1. **Create Flow**: "My First Strategy"
2. **Add Agents**: 
   - Drag "Value Composite" (Warren Buffett style)
   - Drag "Growth Composite" (Peter Lynch style)
   - Drag "Portfolio Manager"
3. **Connect**: Portfolio Analyzer → Both Agents → Portfolio Manager
4. **Configure Portfolio**: 
   - Cash: $100,000
   - Add AAPL: 100 shares @ $150
   - Add MSFT: 50 shares @ $300
5. **Run Backtest**: 
   - Mode: Backtest
   - Dates: 3 months ago to today
   - Click Play
6. **Monitor**: Watch agents work in real-time
7. **Review**: Check dashboard for performance metrics

## Keyboard Shortcuts

- `⌘ + Enter` / `Ctrl + Enter`: Run portfolio analyzer
- `⌘ + B`: Toggle left sidebar (flows)
- `⌘ + I`: Toggle right sidebar (components/agents)
- `⌘ + J`: Toggle bottom panel (output)
- `⌘ + O`: Fit view to canvas
- `⌘ + ,`: Open Settings

---

**Your agents are ready to work!** Just add them to your flow, configure your portfolio, and hit Play! 🎯
