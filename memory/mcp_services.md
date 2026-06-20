# CONNECTED MCP SERVICES

All MCP services are registered here. Never delete entries.

---

## 1. Fetch MCP

- Status: REGISTERED in ~/.claude/settings.json
- Package: @modelcontextprotocol/server-fetch
- Purpose: Fetch web pages and URLs for live news and market data
- Required env vars: none
- Integration: Available to Claude Code as a tool during analysis sessions

---

## 2. Brave Search MCP

- Status: REGISTERED (awaiting BRAVE_API_KEY from user)
- Package: @modelcontextprotocol/server-brave-search
- Purpose: Live web search for economic calendar, news events, market sentiment
- Required env vars: BRAVE_API_KEY (set in ~/.claude/settings.json)
- Integration: Supplements src/skills/news_filtering.py with live search capability
- Note: Get your free Brave Search API key at brave.com/search/api/

---

## 3. Telegram Bot (Outbound Notifications)

- Status: ACTIVE via skill (no MCP required for outbound)
- Implementation: src/skills/telegram_notify.py
- Purpose: Sends trade signals, exit alerts, and daily summaries to Telegram
- Required env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (in .env file)
- Note: For inbound commands (bot receives messages), a Telegram MCP can be added later

---
