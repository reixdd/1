# MIKA v0.3 — desktop companion + public website preview

MIKA is a **research-only** Solana AI companion. This repository contains the existing Windows Tauri desktop, an independent browser UI, and source for an *opt-in* public chat relay backed by the owner's local Ollama model. It never places trades, signs transactions or connects wallets.

## Status

- Desktop UI: market cards have provider-attributed token images, X/Chart links, full-contract Copy, comparative market-cap bars, and model selection that excludes embeddings. The Ollama native request timeout was lengthened for cold starts. **Windows binary requires CI build and on-device verification**.
- Web UI: responsive Scan, Traction, Watch and Ask using only same-origin API routes, not Tauri globals. Public data is fetched only from approved API origins by the Worker. Browser preview is not a deployed website.
- Cloud Worker: Turnstile-verified sessions, signed HttpOnly cookie, strict Origin checks, 3/min and 15/day per visitor, 100/day globally, queue size 8 and concurrency 1. Device requests require a separate secret; the Durable Object owns admission/lease state. **Not deployed**.
- Local connector: optional outbound HTTPS polling from owner's PC to Worker; only reads fixed JARVIS dossier route and talks to Ollama on 127.0.0.1:11434. Default OFF; public serving must be explicitly enabled. **Not installed or enabled**.

## Source structure

- `desktop/`: existing Tauri v0.2 client enhanced with v0.3 features
- `web/`: static public website shell; browser transport, cards, watchlist
- `cloud/`: Cloudflare Worker, Durable Object and tests (preview-only)
- `connector/`: outbound local Ollama connector, opt-in only
- `docs/superpowers/specs/`: accepted architectural design
- `docs/superpowers/plans/`: staged implementation and test plan

## Local source checks

```powershell
cd desktop
npm.cmd test
# to run the Windows desktop from source (requires Rust + C++ Build Tools):
npm.cmd install
npm.cmd run dev
```

Additional Node-only tests: `cd web; npm test`, `cd cloud; npm test`, `cd connector; npm test`. All these tests do not require API credentials or funds.

## Public website deployment: not automatic

**DO NOT DEPLOY before reviewing the security/privacy and terms.** `cloud/wrangler.jsonc` contains placeholder `PUBLIC_ORIGIN` and `TURNSTILE_SITE_KEY`; replace with your domain and Turnstile site key. Configure Worker secrets `SESSION_HMAC_SECRET`, `TURNSTILE_SECRET`, `LOCAL_CONNECTOR_SECRET` in your private Cloudflare account, never in the repository or client. Configure a Cloudflare Workers route and the Durable Object binding. Make sure no open direct ports to Ollama or JARVIS exist. Confirm Turnstile hostname verification, signed-cookie and rate-limit integration, production CSP, quota, pricing, retention, and stop/restart behavior with a real deployment smoke test. The Cloudflare platform may have additional account/plan requirements.

On your Windows PC, the connector must be configured explicitly with `MIKA_PUBLIC_ENABLED=1`, `MIKA_PUBLIC_RELAY_ORIGIN`, `MIKA_PUBLIC_CONNECTOR_TOKEN` (matching Worker secret), and a **text chat model** name in `MIKA_PUBLIC_CHAT_MODEL`. It must never be installed as an automatically-starting service without owner consent. Stop process to revoke live serving; rotate exposed device credentials promptly.

Public messages pass through a cloud relay to your local machine. Provide visitors with a privacy notice and do not collect sensitive personal information.

**Live verification pending:** Cloudflare deploy, Turnstile, real Ollama/JARVIS API connection, provider credentials, and Windows installer smoke test. Never label a missing data field or stale source as live/safe.
