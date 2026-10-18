# MIKA v0.3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans with test-driven-development. Implement tasks independently on isolated branch `mika-v03-public-web-architecture`; never merge to JARVIS main or publish a live endpoint without a security review.

**Goal:** Ship MIKA v0.3 source: enriched Pump.fun token cards, factual Traction and Watch, reliable local Ollama chat, browser-compatible frontend, and a gated cloud job relay served by local AI.

**Architecture:** Preserve Tauri shell and abstract public versus local research transport. Model read-only evidence, keep data source/freshness, run public conversations through a guarded queue and an outbound-only local connector. The website must not reach JARVIS/Ollama directly.

**Tech Stack:** Tauri 2/Rust, ES modules/Node test runner, Cloudflare Workers + Durable Objects, optional website static hosting.

**Spec:** `mika/docs/superpowers/specs/2026-10-18-mika-v03-public-web-relay-design.md`

## Global Constraints

- Existing JARVIS main and DIT untouched. No wallet, trade, signing, swaps or automated advice.
- Media/socials only from source metadata; URLs are validated, image fallback is honest.
- One-second UI polling is *not* proof of one-second upstream data updates.
- Local Ollama stays on loopback; device connector uses outbound requests only.
- Public service is disabled by default; don't deploy until secrets, abuse tests and owner approval.

## Review Focus

1. Malformed or JavaScript social URL must never become clickable; X domains restricted and links open safely.
2. Falsely reported Pump.fun provenance must never enter New Pairs; preserve already confirmed classification.
3. Market cap comparisons cannot divide by zero or turn missing into a numeric zero.
4. Public visitor cannot select arbitrary model, endpoint or role; signed sessions and device leases must be validated.
5. Local Ollama cold-start/timeout and offline states must not be disguised as AI responses.

---

### Task 1: Token media, social normalization and visual comparison

**Files:** `mika/desktop/ui/live-feed.mjs`, `domain.mjs`, new `token-media.mjs`, `app.mjs`, `styles.css`, `index.html`, `mika/desktop/tests/metadata-v03.test.mjs`.

**Interfaces:** `normalizeSocials(raw): Array<{kind,url}>`, `safeImageUrl(url): string|null`, `marketCapRelative(cap,max):number|null`.

- [ ] Write tests for legitimate DEX Screener `info.imageUrl` and socials, rejected malicious URLs, merged provider metadata, proportional bars, exact mint preservation.
- [ ] Run `node --test tests/metadata-v03.test.mjs` and observe RED.
- [ ] Implement normalized metadata, token imagery fallback, token cards, one-click full CA copy, source/chart/X links, bar with explicit scale.
- [ ] Re-run full `npm test` and DOM smoke checks; observe GREEN.
- [ ] Commit on isolated branch.

### Task 2: Ollama health and chat reliability

**Files:** `mika/desktop/src-tauri/src/main.rs`, `mika/desktop/ui/app.mjs`, `mika/desktop/ui/data.mjs`, `mika/desktop/tests/chat-v03.test.mjs`.

**Interfaces:** `selectChatModel(models,preferred)`; text-only response validation; native Ollama client independent 90s timeout; constrained owner-selected model.

- [ ] Test first for model picker (exclude embeddings, prefer conversational model), retryable offline state and correctly bounded history.
- [ ] Run tests RED.
- [ ] Fix Tauri native Ollama-only timeout and HTTP bounded response; show model errors and help text, not fake dialogue.
- [ ] Run JS suite, syntax checks and Windows CI; report native limitations.
- [ ] Commit isolated changes.

### Task 3: Browser transport and read-only website

**Files:** new `mika/web/index.html`, `mika/web/transport.mjs`, `mika/web/app.mjs`, `mika/web/styles.css`, `mika/web/package.json`, `mika/web/tests/transport.test.mjs`.

**Interfaces:** `createWebTransport(fetchImpl)` exposing `feed,quotes,token,chatSession,submitChat,chatStatus`; shared public read-only data contracts.

- [ ] Write transport tests for same-origin API, no arbitrary URLs and graceful errors; run RED.
- [ ] Build responsive browser view reusing domain cards and without Tauri globals; no locally hosted secrets or mock live prices.
- [ ] Run tests and a static serving smoke check; commit separately.

### Task 4: Cloud queue, admission and outbound local worker

**Files:** new `mika/cloud/wrangler.jsonc`, `mika/cloud/worker.mjs`, `mika/cloud/coordinator.mjs`, `mika/cloud/tests/security.test.mjs`, `mika/connector/connector.mjs`, `mika/connector/package.json`, `mika/connector/README.md`.

**Interfaces:** visitor session after verified Turnstile, `POST /api/chat/jobs`, `GET /api/chat/jobs/:id`, device-only claim/complete/heartbeat; all operations require fixed limits and secret.

- [ ] Write tests for auth, job ownership, unauthenticated access, quota, device token and duplicated completion; observe RED.
- [ ] Implement minimum secure admission coordinator, lease, expiration, capacity, bounded requests; outbound connector with owner-configured secret and localhost allowlisted Ollama endpoint only.
- [ ] No public deploy or secret provisioning. Run all tests GREEN, separate self-security review, record any failures or unsupported real-cloud behavior.
- [ ] Commit as preview-only source.

### Task 5: Release evidence and handoff

**Files:** `mika/README.md`, `mika/VALIDATION.md`, `mika/docs/superpowers/progress-v03.md`.

- [ ] Verify Node suites, Rust build via GitHub Actions when available, and source diff.
- [ ] Run public abuse/replay regression tests, check local-only URL exposure, security settings, data freshness and offline behavior.
- [ ] Link commit/tree and deliver source/build artifact only after tests pass.
- [ ] Explicitly list live-provider tests and public deployment as pending until owner device/Cloudflare setup.
