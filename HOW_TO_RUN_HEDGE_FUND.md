# How to Run Your Hedge Fund via the Web UI

## Quick Start Guide

Your hedge fund web application is already set up and running! Here's how to use it:

## Step 1: Access the Web Interface

1. **Open your browser** and go to: `http://localhost:5173`
2. The UI should already be running (both frontend and backend are active)

## Step 2: Configure API Keys

To run the hedge fund, you need at least **one LLM API key**. You can add API keys in two ways:

### Option A: Via the Web UI (Recommended)
1. Click the **Settings icon** (⚙️) in the top bar, or press `Shift + Cmd + ,` (Mac) / `Shift + Ctrl + ,` (Windows)
2. Navigate to the **"API Keys"** section
3. Add at least one of these API keys:
   - **OpenAI API Key** (for GPT-4o, GPT-4o-mini, etc.)
   - **Groq API Key** (for DeepSeek, Llama3, etc.)
   - **Anthropic API Key** (for Claude models)
   - **DeepSeek API Key** (for DeepSeek models)
   - **Google API Key** (for Gemini models)
   - **OpenRouter API Key** (for various models)
4. API keys are **automatically saved** as you type

### Option B: Via .env File
1. Edit the `.env` file in the project root
2. Add your API keys:
   ```bash
   OPENAI_API_KEY=your-key-here
   GROQ_API_KEY=your-key-here
   # etc.
   ```
3. Restart the backend server

**Note:** API keys added via the UI are stored in the database and take precedence over .env file keys.

## Step 3: Set Up Your Portfolio

1. In the main flow view, you'll see a **"Portfolio Analyzer"** node
2. Click on it to configure:
   - **Available Cash**: Starting capital (default: $100,000)
   - **Positions**: Add stock positions with:
     - Ticker symbol (e.g., AAPL, MSFT, NVDA)
     - Quantity
     - Trade price

## Step 4: Configure Agents

1. The flow shows various **agent nodes** (analysts) connected to your portfolio
2. Click on any agent node to:
   - Select which **language model** to use
   - Configure agent-specific settings
3. You can:
   - **Add agents** from the left sidebar
   - **Connect agents** by dragging edges between nodes
   - **Remove agents** by selecting and deleting them

## Step 5: Run the Hedge Fund

1. Click the **Play button** (▶️) on the Portfolio Analyzer node
2. Or press `Enter` while the node is selected
3. The system will:
   - Stream real-time updates from each agent
   - Show progress as each analyst evaluates the stocks
   - Display final investment recommendations

## Step 6: View Results

- **Agent Output**: Click on any agent node to see their analysis
- **Final Report**: Check the "Investment Report" node for the final recommendations
- **JSON Output**: View raw data in the JSON output node

## Running a Backtest

1. In the Portfolio Analyzer node, switch to **"Backtest"** mode
2. Set your **start date** and **end date**
3. Click **Play** to run a historical backtest
4. View performance metrics and day-by-day results

## Keyboard Shortcuts

- `⌘ + ,` (Mac) / `Ctrl + ,` (Windows): Open Settings
- `Enter`: Run selected node
- `⌘ + B`: Toggle left sidebar
- `⌘ + I`: Toggle right sidebar
- `⌘ + J`: Toggle bottom panel
- `⌘ + O`: Fit view to canvas

## Troubleshooting

### "No API keys configured"
- Go to Settings → API Keys and add at least one LLM API key
- Make sure the key is valid and has credits

### "Backend connection failed"
- Check that the backend is running at `http://localhost:8000`
- Open `http://localhost:8000/docs` to verify the API is accessible

### "Agents not running"
- Verify you have at least one valid API key configured
- Check the browser console for error messages
- Ensure the selected models are available with your API keys

## Supported Stock Tickers

**Free (no API key needed):**
- AAPL (Apple)
- GOOGL (Google)
- MSFT (Microsoft)
- NVDA (NVIDIA)
- TSLA (Tesla)

**Other tickers require:** `FINANCIAL_DATASETS_API_KEY` in Settings

## Need Help?

- Check the API documentation: `http://localhost:8000/docs`
- View backend logs in the terminal where you ran `./run.sh`
- Check browser console (F12) for frontend errors

---

**Ready to go!** Your hedge fund is set up and ready to run. Just add your API keys and click Play! 🚀
