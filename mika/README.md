# MIKA v0.2 — Local research companion

MIKA is a **research-only** Windows 11 desktop sidecar, powered by a separate Tauri 2 shell and the existing JARVIS research core. It does not operate wallets, make transactions, rank winning coins, or offer investment recommendations.

## What's changed in this candidate

- Scan combines read-only GMGN Trenches and independently retrieved GeckoTerminal new pools with **confirmed Pump.fun DEX/launchpad provenance**. JARVIS's narrow canonical radar no longer blocks an otherwise available public launchpad feed. Unsupported launchpads are excluded; unverified platform identity does not produce a guessed token.
- Watch displays full contract addresses with Copy, requests current DEX Screener market-cap observations, and labels provider/request timestamps.
- Traction shows the observation queue even before two comparable snapshots exist. Material changes require compatible provider/pool and at least two timestamps.
- Ask MIKA now calls **local Ollama text chat**, with short conversational history, automatically enumerating installed models, and selected-token context. She can have casual conversation outside market topics. Tone is friendly, skeptical, and playful but not immersive-romantic.
- MIKA requests one batch of up to 30 token quotes per second when tokens are present, rotates larger watchlists, and backs off after errors. **This is request cadence, not guaranteed 1-second fresh market data.** Provider caching is out of MIKA's control.

## Sources and limits

- JARVIS Core (localhost port 8768): GMGN read-only CLI, evidence summaries where available.
- GeckoTerminal public API: confirmed Pump.fun DEX new pools, fetched roughly every 40 seconds; actual coverage is limited by caching and availability.
- DEX Screener public API: read-only quotes for up to 30 token addresses per request. Its documented token endpoint request limit is 300/minute; MIKA requests approximately 60/minute at most for the quotes task, and stops/backoffs on failures.
- Ollama (localhost port 11434): local chat, no cloud fallback.

A provider may legitimately return no confirmed Pump.fun pools. MIKA must show an empty state rather than inventing tokens. New-pool feeds are not a complete or instant firehose of every launch.

## Running from source on Windows

Prerequisites: Node.js 20+, Rust 1.90+, Microsoft Visual Studio C++ Build Tools, WebView2. Existing JARVIS Core at `http://127.0.0.1:8768` is recommended but not necessary for GeckoTerminal/DEX read-only data.

```powershell
cd mika\desktop
npm.cmd install
npm.cmd test
npm.cmd run dev
```

For local Ask MIKA, start Ollama and ensure at least one model is installed. If unavailable, the UI reports that; it does not pretend to chat. The first available local model is selected, preferring `qwen3.5:4b` if present. Never paste secrets, private keys or passwords into chat.

**This source-only candidate needs a successful Windows Tauri build and live-provider smoke test before an installer can be called verified.** Run `npm.cmd run build` to build it on your Windows environment.

## Open-source research skill

`skills/market-research/SKILL.md` describes an embedded read-only behavior policy. It is **not** a separately installed GMGN/agent framework extension. Avoid installing trading, swapping or account-management skills into this read-only sidecar.

## Repository isolation

Original project lives in `reixdd/1` on a MIKA-specific branch under `mika/`; do not merge into JARVIS main. DIT and Supabase remain untouched.

## MIKA 0.4.1 research-only discovery hotfix

- Scan and Traction include only tokens with source-supplied, validated X or Telegram links. Missing social information stays excluded; official project identity and safety are not established by a social account.
- Excludes launchpad records tagged Mayhem or Mayhem agent. A pool/DEX label by itself does not establish standard Pump.fun origin; such Gecko-only candidates are withheld when origin is unknown. This may leave fewer entries or an empty feed when GMGN is unavailable.
- Retains X, Telegram, and website links from multiple provider records, rather than silently replacing one with another.
- Traction defaults to Within limits; unverified bundle metrics have their own category and do not pass an enabled bundle threshold. A first-sighting market-cap change uses compatible provider/pool observations, is historical, and is not predictive.
- Settings are displayed in an accessible, visible floating drawer with Escape to close.
- Provider polling, request rate limits, cached values and absent metadata can delay new matches. All information is research-only, not a reason to trade.
