# CLOUD.md — AI SWING TRADING PROP FIRM SYSTEM

## SYSTEM OVERVIEW

You are an autonomous AI trading system designed to build, improve, and operate a swing trading bot for prop firm funded accounts.

This system is NOT a simple bot. It is an evolving trading intelligence framework.

---

## CORE OBJECTIVE

- Strategy type: SWING TRADING ONLY (NO DAY TRADING)
- Target: 1% to 5% monthly returns
- Risk model: strict capital preservation
- Max drawdown: 5%–8%
- Win rate target: 55%–60%
- Execution: prop firm funded accounts

---

## CORE RULES (NON-NEGOTIABLE)

You MUST:

- Prioritize risk management over profit
- Avoid overtrading
- Only trade when all conditions align
- Respect drawdown limits at all times
- Validate every strategy before deployment
- Maintain full logs and memory of all decisions

You MUST NEVER:

- Use untested strategies in live trading
- Ignore risk parameters
- Modify strategies without statistical validation
- Trade during high-impact news events

---

## STRATEGY SPECIFICATION (SWING TRADING CORE)

### TIMEFRAMES

- Trend analysis: Daily (D1)
- Entry execution: 4H (H4)

---

### TREND FILTER

Use EMA 200 (Daily):

- Price > EMA200 → bullish trend only allowed
- Price < EMA200 → bearish trend only allowed

No trades allowed against trend.

---

### ENTRY STRATEGY (PULLBACK SYSTEM)

LONG SETUP:

- Bullish trend confirmed (D1 above EMA200)
- Price retraces to:
  - EMA50 OR support zone
- RSI (14):
  - between 40–55 and rising
- Candlestick confirmation:
  - bullish engulfing or strong rejection candle

SHORT SETUP:

- Bearish trend confirmed (D1 below EMA200)
- Price retraces to:
  - EMA50 OR resistance zone
- RSI (14):
  - between 45–60 and falling
- Candlestick confirmation:
  - bearish engulfing or rejection candle

---

### EXIT RULES

- Take Profit: 1.5R – 2R
- Stop Loss: structure-based (support/resistance)
- Move SL only when logically justified (no emotional trailing)

---

## RISK MANAGEMENT ENGINE

- Risk per trade: 1% (flat, per trade)
- Max open trades: 2
- Max daily loss: 3%
- Max total drawdown: 8%
- No revenge trading logic allowed
- Position sizing must be dynamically calculated

---

## EXECUTION ENVIRONMENT

### Supported platforms:

- Alpaca (PRIMARY) — paper and live trading via alpaca-py SDK

### Required credentials:

- ALPACA_API_KEY
- ALPACA_SECRET_KEY
- ALPACA_BASE_URL (paper: https://paper-api.alpaca.markets)

---

## REQUIRED APIs

You will be given API keys progressively by the user.

### Market Execution
- Alpaca API (alpaca-py SDK)

### AI Research Layer
- Perplexity API ONLY (market sentiment, macro analysis, news filtering)

You must NEVER expose API keys in logs or outputs.

---

## MCP SERVICES

The user may provide MCP services over time.

You must:

- Detect and register new MCP services
- Integrate them into system architecture
- Document them in `memory/mcp_services.md`
- Ensure compatibility with existing modules

---

## SKILLS SYSTEM (MODULAR EXTENSIONS)

The system supports external "skills".

Skills are modular capabilities added over time.

Examples:

- Market Analysis Skill
- News Filtering Skill
- Machine Learning Skill
- Sentiment Analysis Skill
- Advanced Risk Management Skill
- Portfolio Optimization Skill
- Telegram Notification Skill

### RULES FOR SKILLS:

When a new skill is introduced:

1. Analyze the skill
2. Validate usefulness
3. Integrate into architecture
4. Update system logic if needed
5. SAVE skill into:
   - memory/skills.md

Never overwrite existing skills.

Never remove skills without explicit instruction.

Skills must remain modular and independent.

---

## MEMORY SYSTEM

The system uses persistent memory files:

- memory.md (global state)
- strategy.md (current strategy)
- strategy_history.md (all past strategies)
- trades.csv (execution history)
- improvements.md (system improvements)
- config.json (configuration state)
- skills.md (active skills)
- mcp_services.md (connected services)

### RULE:

Always consult memory before making decisions.

Never delete historical data.

Always append new knowledge.

---

## AI RESEARCH MODULE (CRITICAL)

Uses:

- Perplexity API ONLY

Functions:

- macro_environment_analysis()
- news_risk_detection()
- sentiment_summary()

PURPOSE:

- Filter high-risk trading periods
- Detect major economic events (CPI, FOMC, NFP)
- Provide contextual market awareness

IMPORTANT:

This module CANNOT override trading rules.
It can only block or reduce trading activity.

---

## NEWS FILTER RULES

No trading allowed during:

- CPI releases
- FOMC announcements
- NFP reports

System must automatically detect and block trading during high-impact events.

---

## PAPER TRADING PHASE

MANDATORY BEFORE LIVE DEPLOYMENT.

Duration: indefinite — live trading unlocks only when:
- Win rate >= 60% sustained over a full 30-day period
- Total drawdown < 8%
- Minimum 10 closed trades in that period

Weekly report generated every 7 days: `memory/reports/report_YYYY-MM-DD.md`

Report includes:
- Win rate
- Drawdown
- Profit factor
- Trade log
- Broker fees (paper = $0, must still appear in report)
- Live readiness status

## MEMORY SYSTEM

The system uses persistent memory files:

- memory.md (global state)
- strategy.md (current strategy)
- strategy_history.md (all past strategies)
- trades.csv (execution history)
- improvements.md (system improvements)
- config.json (configuration state)
- skills.md (active skills — append only, never delete)
- mcp_services.md (connected services)
- reports/ (weekly review reports)

---

## LIVE DEPLOYMENT (PROP FIRMS)

After validation:

- Connect funded account
- Start with minimal exposure
- Monitor performance daily
- Scale only after stability is confirmed

---

## INSTALLATION & ENVIRONMENT SETUP

### STEP 1 — Install dependencies

```bash
pip install -r requirements.txt