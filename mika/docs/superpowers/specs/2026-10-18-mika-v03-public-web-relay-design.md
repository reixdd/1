# MIKA v0.3 — Public Web, Market Research and Local AI Relay Design

**Date:** 2026-10-18
**Status:** Written for user review. Approved direction: public visitors may chat through a protected relay; publishing and implementation require subsequent reviews.
**Source branch:** `reixdd/1:mika-v02-research-upgrade`
**Destination branch:** `mika-v03-public-web-architecture`
**Scope:** Architectural specification only. No public services, DNS, tunnels, secrets or trading systems are provisioned in this step.

## 1. Intent and success criteria

MIKA stays a compact Windows research companion and becomes a responsive public website using the same presentation and normalized research contracts. Visitors see factual, source-attributed Solana launch observations, artwork, links, market-cap comparisons, and observed activity changes. Public visitors may talk casually with MIKA and ask about supported research through the owner's **local** Ollama model. The website remains usable when the owner's PC is offline, while chat clearly reports that local AI is unavailable.

MIKA never manages wallets, places orders, ranks guaranteed winners, or provides buy/sell recommendations. Provider-derived flags are evidence, not proof. This design does not publish JARVIS operator privileges or expose local Ollama directly.

### Explicit user choices

- Public (not owner-only) AI conversation through local models, controlled by a secure, rate-limited cloud relay.
- Retain the MIKA dark/lavender character-driven shell and support desktop plus future website.
- Display real token images when provided; X/social links only when supported by token metadata.
- Scan: rolling, proven Pump.fun-originated token observations without fabricated entries.
- Traction: actively updated observations, market-cap visual bars and factual changes.
- Watch: full mint visible/copyable; updated market cap with verified observation time.
- Ask: genuine multi-turn local AI conversation, not a keyword-scripted explainer.

## 2. Alternatives and decision

**Selected: public Cloudflare Worker + Durable Object admission/queue + outbound-only Windows connector.** Browser requests reach the Worker; a dedicated device connector polls or holds an outbound authenticated connection to a single job queue. It runs permitted local Ollama inference and returns bounded responses over outbound HTTPS. No inbound port, public local-server URL, or Cloudflare Tunnel to Ollama is necessary. This is preferred because the public internet never has routable access to JARVIS or Ollama, and global admission can be enforced in one durable coordinator.

**Alternative A: Cloudflare Tunnel into a local HTTP gateway.** Less initial infrastructure, but configuration errors can bypass edge controls and expose a local origin. Rejected for public anonymous chat.

**Alternative B: Supabase Edge Functions plus database-backed job queue.** Auth, RLS and persistence integrate well with the existing stack, but a distinct queue/polling system and cross-project isolation are needed. Rejected for MVP; optional later for user-owned watchlists. Do not reuse DIT treasury/worker tables.

Cloudflare Worker rate-limit bindings are useful for coarse abuse defense but counters are location-local; the Durable Object's atomic admission and global quota are the source of truth for model capacity.

## 3. Trust boundaries and runtime

```
Public browser (web/)  ──HTTPS──>  Cloudflare Worker
  Scan/Traction/Watch UI             ├─ public, sanitized, cached market evidence
  MIKA Ask chat                      └─ Turnstile, session, quota, global admission
                                         │
                                   Durable Object coordinator
                                   jobs + short-lived responses
                                         ▲ outbound HTTPS pull/push ONLY
                                         │
                                  Local connector (Windows)
                                         ├─ Ollama 127.0.0.1:11434, fixed allowlisted model
                                         └─ JARVIS 127.0.0.1:8768, GET-only curated evidence
```

The connector is a **separate least-privilege service**, not the Tauri WebView. It obtains server-authenticated queued jobs and sends results. It must not receive arbitrary URLs, paths, model names, tool invocations, JSON-RPC instructions or executable commands from browser messages. Remote visitors cannot invoke JARVIS endpoints: a visitor message may provide only plain text and an optional validated Solana mint that maps to a predefined read-only dossier projection.

The desktop app may run the same local connector to serve public chats, but must show a visible ON/OFF public-serving switch, active session count and daily quota. Default public serving OFF until the owner explicitly enables it. Closing the owner app or disabling the connector leaves the public site online with AI OFFLINE.

## 4. Public chat protocol and security

### Visitor API (same-origin HTTPS)

- `POST /api/chat/session`: server-verify anti-bot challenge, issue a short-lived, signed, HttpOnly, Secure, SameSite=Lax browser session cookie. Token is scoped to MIKA chat, not local device access. Do not accept caller-supplied identity or model IDs.
- `POST /api/chat/jobs`: accepts `{text: string, selected_mint?: string}`, CSRF/Origin and session verification, bounded text length, quota/queue checks; returns `{id,status:"queued"}` or 429/503 with explicit retry metadata.
- `GET /api/chat/jobs/:id`: only owning session retrieves `queued|running|complete|error|expired` and bounded output; initial implementation uses polling, streaming can be added using SSE later.
- `DELETE /api/chat/jobs/:id`: allow owner-session cancellation.

### Device-only API (outbound from local connector)

- `POST /api/device/claim`: authenticate via an **owner-provisioned, rotatable device credential** (never embedded in web JS, repo or bundled installer); claim one queued job with a lease.
- `POST /api/device/complete`: authenticated completion with job ID and lease ID, capped output, replay protection.
- `POST /api/device/heartbeat`: update ephemeral online/capacity flag; public status reports AI offline if heartbeat expires.

### Proposed MVP limits (configurable by owner)

- 600 Unicode characters per public message; maximum 8 prior role-validated turns in model context.
- 3 submitted jobs per visitor per 60 seconds; 15/day per visitor; 100/day global.
- One Ollama job executing at a time and at most 8 pending jobs. Overflow yields 429/503, never unbounded buffering.
- Generation budget: 256 output tokens, max 90-second running lease, separate cold-start budget up to 120 seconds, then timeout with an honest error. Lease reissue must be idempotent.
- Session lifetime 24 hours; completed/failed job text retained no longer than 60 minutes; no raw chat telemetry by default. Metrics store counts, timing buckets and status, not prompt/response bodies.
- Owner-controlled kill switch, quota reset and device credential rotation.
- Rate limit by signed browser session plus anti-bot protections; never rely solely on IP or the Worker regional limiter.
- Typed, restrictive, JSON schema-validated payloads; disallow arbitrary URLs, system roles and tool calls. Bounded response size, method/path allowlists, CSP, HTTPS, same-origin web APIs, strict secret separation.

### Model selection and behavior

Only configured owner-approved local text models run. MVP serves a single efficient model (prefer `qwen3.5:4b` if installed and validated); do not expose embeddings or all installed models to visitors. Local owner may inspect alternate models privately. A failed warmup or model timeout reports unavailable rather than generating a scripted fake reply.

System persona: MIKA is a witty, kind, slightly teasing research companion with general casual conversation ability; never immersive romance. Separate deterministic market evidence from language generation. Token names, URLs and descriptions are untrusted data; no instructions from those fields can override the system. No order placement, signing, wallet operations or buy/sell calls. Provide uncertainty about highly speculative assets.

Model input includes only tightly redacted public research: requested valid mint, observed token/pool metrics, risk findings with provenance, uncertainty and timestamps. Never expose operator credentials, wallet addresses that are secret, hidden file contents, local paths or server environment.

### Privacy note

The local model performs inference, but public visitor messages pass through Cloudflare's relay in transit. The website must disclose this, along with retention and the fact that chat is unavailable when the owner's PC/connector is offline.

## 5. Shared frontend and market metadata

Preserve v0.2 Tauri app. Introduce transport abstraction:
- `desktop/ui/transport.mjs`: `getFeed()`, `getQuotes(mints)`, `getToken(mint)`, `chat(text,context)` routed via Tauri native commands.
- `web/src/transport.mjs`: same model, using only same-origin public Worker endpoints. No `window.__TAURI__` reference on the website.
- Shared platform-neutral domain, token cards, state, chart-bar, character and persistence modules are extracted from the current 66-line dense `app.mjs`; app boots with transport injected, no arbitrary local network URL.

### Image and social metadata fixes

DEX Screener token pairs expose `info.imageUrl`, `info.websites` and `info.socials`. Normalize and preserve these, plus compatible trusted GMGN/Gecko fields where available. Accept only valid absolute HTTPS URLs from known image hosts or serve through a bounded, allowlisted image cache. Default to letter/MIKA placeholder when absent; do not invent token art. Enforce CSP for the exact approved image hosts and handle load errors safely.

Show X button only for source-provided Twitter/X handle or URL; reject JavaScript URLs and malformed or deceptive hosts. External links use `rel="noopener noreferrer"` and visibly identify the provider. Show one-tap full mint copy, a visible full-address disclosure, and an independent chart/source link. Never infer social handles from token tickers.

### Scan, Traction, Watch

**Scan:** rolling Pump.fun-proven rows, token artwork, symbol/name, mint copy, source age, provider, market cap, liquidity, 5m buys/sells and volume; investigator status is `UNVERIFIED` whenever essential evidence is absent. Explicit fresh/delayed/unavailable badges.

**Traction:** ranks *observed relative activity changes* from compatible timestamped pairs without predicting winners or recommending purchases. Show artwork, timestamp, change metrics, a market-cap comparison bar with a clear scale and selected sorting controls. The bar is comparative display, never a safety rating. With a single snapshot show "baseline gathering", not an invented trend. The desktop can render the clock each second; provider refreshes remain bounded by source rate limits/cache.

**Watch:** artwork/social/chart, full mint + copy, last verified market cap and observation time; watch status persists locally in desktop and browser-local storage on public web. Do not promise synced user accounts for v0.3.

**Ask:** conversational user/MIKA bubbles, selected-token evidence, clear available/queued/typing/offline/limited/error states, 100% local inference through the connector. Desktop uses local Ollama transport; public web uses the protected relay.

## 6. Public market-data provider architecture

Public Worker fetches *only explicitly allowlisted market API endpoints* and returns normalized, bounded, cached data with per-field provenance and observation time; never lets browsers provide arbitrary upstream URLs. Alternatively ingest public-safe, sanitized snapshots outbound from local JARVIS through a separate, authenticated operation, not its raw API. Provider selection retains launchpad provenance so ordinary Solana pairs are not misrepresented as Pump.fun-originated.

Respect provider licensing, caching and rate-limit terms. Keep public feed independent from local Ollama status. Caches, API timeout and 429s result in source/status labels, stale data explicitly marked, not manufactured zero values.

## 7. Failure handling, monitoring and rollback

- Owner PC or Ollama offline: show AI OFFLINE and retain market research. No remote wake or device access.
- Full queue / global quota reached: 429 with retry details. No unlimited backlog.
- Device job worker crashes: lease expires once; idempotent retry or explicit error, never duplicate responses.
- Cloud relay unavailable: public chat disabled, local desktop can still use direct local Ollama.
- Market API fails: preserve last observed snapshot with timestamp; do not call it live.
- Conflicting provider data: surface labels and source URLs; no favorable risk default.
- Chat abuse: bot gate, per-session and global limits, kill switch, rate metrics and temporary session block. No internet-search tool calls from the model.
- Public deployments behind separate versioned branches and preview URL. Roll back by reverting Worker/frontend release; do not change JARVIS or DIT.

## 8. Component ownership and delivery sequence

This architecture is intentionally broken into independently reviewable implementation stages:

**A — Market metadata and UI repair (desktop first):** normalize images/socials, proper cards, chart/source links, market-cap bars, full mint copies and frontend tests. Retain working v0.2 installer until replacement passes CI and live smoke tests.

**B — Local Ollama reliability + portable frontend:** streaming or chunk progress where supported; dedicated longer generation timeout, model availability diagnostics, prompt/context sanitation; split desktop UI into platform-independent components and transport. Local chat needs an actual conversation verification, not a model dropdown alone.

**C — Public web app + relay + outbound Windows connector:** Cloudflare Worker, Durable Object queue, user anti-bot session, centralized admission, minimal local connector and public web Ask. Publish only after abuse/security tests pass and owner explicitly enables public serving.

**D — Production verification:** source/provider integration tests; unauthenticated spoofing, replay, CSRF, SSRF and path traversal tests; 100-request concurrency/load test with CPU/capacity budget; restart/reconnect tests, privacy retention checks; Windows build and web deploy preview. No production launch before owner verifies domain/Cloudflare account and quotas.

All stages require test-first implementation, independently verifiable commits and a clear difference between mock tests and live-provider proof. New public infrastructure requires an explicit deploy action after review. No service creation, credentials, domains, databases, live chat endpoints or user funds are affected by this design document.

## 9. Acceptance tests

1. Provider response with `info.imageUrl` and X social item produces the correct image and link; malicious or missing URLs are discarded.
2. 10 real mint entries produce 10 token cards with no invented pictures and mint-copy returns the exact original case-sensitive address.
3. Two compatible market snapshots produce a factual traction change and correctly scaled market-cap bar; one snapshot produces baseline-gathering message.
4. Desktop still opens at 390–420px and web layout works from phone to desktop without Tauri globals.
5. A user can start a chat anonymously only after server-verified challenge and session issuance; bypass/cookie tampering fails.
6. One device worker consumes one queued job and returns a short answer; duplicate completion or stolen lease is rejected.
7. Local Ollama is never publicly reachable through the app; arbitrary JARVIS paths, model names, files, localhost URLs and commands are rejected.
8. Many visitors cannot exceed a strict global in-flight/queued/quota cap; rate limits cannot be trivially bypassed by changing browser session.
9. Offline and timeout behavior is truthful; no fallback cloud LLM or scripted fake responses.
10. No changes to JARVIS main, DIT workers, wallets, secrets or treasury.
