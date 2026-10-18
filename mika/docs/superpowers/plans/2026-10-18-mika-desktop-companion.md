# MIKA Desktop Companion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, with test-first checks for each task. Keep this project on an isolated branch or, after migration, in its own repo. Do not merge this branch into JARVIS main.

**Goal:** Deliver a standalone Windows Tauri sidecar that reads real JARVIS/GMGN research data, preserves provenance and unknowns, tracks changes, and presents an animated MIKA companion. Transactions disabled.

**Architecture:** MIKA owns a separate presentation client and local preferences. Its native command bridge is restricted to an allow-list of JARVIS GET routes on `127.0.0.1:8768`. JARVIS remains the canonical scanner; MIKA only consumes observations and holds user-facing watch preferences/history. In this staging repository all paths below are relative to `mika/`.

**Tech Stack:** Tauri 2 (Rust + native Windows WebView), plain HTML/CSS/ES modules, Node built-in test runner, localStorage for first-shell preferences, optional SQLite for durable historical observation milestone. Production database schema is explicitly deferred until Milestone B.

**Spec:** `docs/superpowers/specs/2026-10-18-mika-desktop-companion-design.md`.

## Global constraints

- Windows 11; target default width 390–420px, resizable and optionally always-on-top.
- JARVIS Core stays on `http://127.0.0.1:8768` by default; no new scanner, private keys, swaps, orders, or POST operations to JARVIS.
- Do not alter or delete `reixdd/1` main, its data ownership, or Dead Internet Theory/Supabase.
- Display `UNKNOWN` for missing security evidence, never replace null with zero; never claim a memecoin is safe.
- Token identity is chain+mint; pool IDs are preserved separately.
- The LLM never sets the deterministic risk verdict.
- Source timestamps and providers must be visible; "LIVE" status only when data is fresh.
- Generated character concept boards are references, not validated aligned sprite frames; use a static artwork fallback with lightweight CSS animations in MVP.
- No browser clipboard monitoring or GMGN DOM scraping.

## Review focus / failure conditions

1. Multiple pools for one token: one watchlist token, separate pool metrics; test in Task 2.
2. Dossier 404 for unknown new token: display GMGN fallback, do not fabricate canonical history; test in Task 3.
3. Missing/NaN security metrics: remain UNKNOWN, not safe; test in Task 4.
4. Rate limiting, offline, malformed JSON: show backoff/errors and cached state with timestamp; test in Task 3.
5. Unauthorized localhost routes and newline path injection: reject before connecting; test in Task 1.

---

### Task 1 — Standalone Tauri shell and local read-only bridge

**Files:**
- Create `desktop/src-tauri/Cargo.toml`, `desktop/src-tauri/build.rs`, `desktop/src-tauri/tauri.conf.json`, `desktop/src-tauri/src/main.rs`, `desktop/ui/index.html`, `desktop/package.json`.
- Test: Rust unit tests in `desktop/src-tauri/src/main.rs` and Windows `cargo test`.

**Interfaces:**
- `core_get(path: String) -> Result<String, String>` native command; GET-only allowlist: `/health`, `/api/operator/{radar,dossier,chart,gmgn/status,gmgn/trenches,gmgn/token}`, `/api/attention`, `/api/models`.

- [ ] Step 1: Add tests that reject unexpected paths, CR/LF, off-host URLs and POST-like routes.
- [ ] Step 2: Run `cargo test`; confirm tests fail before implementation.
- [ ] Step 3: Implement strict allowlist and bounded HTTP read/parse, no shell invocation, no arbitrary URL entry.
- [ ] Step 4: Run `cargo test` and `cargo check`; verify native window opens on Windows.
- [ ] Step 5: Commit `feat(mika): isolate secure read-only Windows sidecar`.

### Task 2 — Canonical domain and freshness

**Files:** `desktop/ui/domain.mjs`, `desktop/tests/domain.test.mjs`.

**Interfaces:** `tokenKey(chain, contract)`, `groupMarkets(rows)`, `freshness(observedAt, now)`, `normalizeRadarRow(row)`.

- [ ] Step 1: Tests verify Solana address case preservation; two pools collapse to one token; absent data stays null; 45/180 second freshness boundaries.
- [ ] Step 2: Run `node --test desktop/tests/domain.test.mjs`; confirm RED.
- [ ] Step 3: Implement functions with numeric validation and source attribution.
- [ ] Step 4: Run tests; confirm GREEN.
- [ ] Step 5: Commit `feat(mika): canonicalize market rows with source freshness`.

### Task 3 — Real provider adapter and graceful fallback

**Files:** `desktop/ui/data.mjs`, `desktop/tests/data.test.mjs`.

**Interfaces:** `createClient(coreGet)` exposing `status()`, `radar()`, `token(chain,address)`, `gmgnStatus()`, `attention()`.

- [ ] Step 1: Stub bridge tests for offline, malformed JSON, 404 dossier and direct GMGN token fallback; check source labels.
- [ ] Step 2: Run tests; confirm RED.
- [ ] Step 3: Implement adapter with bounded retries/backoff, no fabricated result and unknown states.
- [ ] Step 4: Run tests; confirm GREEN.
- [ ] Step 5: Commit `feat(mika): connect real JARVIS research views`.

### Task 4 — Evidence-first risk display, not a safety score

**Files:** `desktop/ui/risk.mjs`, `desktop/tests/risk.test.mjs`.

**Interfaces:** `classifyRisk(findings)` returns `HIGH_RISK|NEEDS_REVIEW|NO_MAJOR_FLAGS_DETECTED|UNVERIFIED`, reasons and unknowns.

- [ ] Step 1: Tests assert missing authority/holder checks cannot return favorable verdict; contradictory evidence is flagged; independently observed findings preserve provider class.
- [ ] Step 2: Run tests; confirm RED.
- [ ] Step 3: Implement transparent rule logic (configurable thresholds), never call LLM for verdict.
- [ ] Step 4: Run tests; confirm GREEN.
- [ ] Step 5: Commit `feat(mika): evidence-based risk review`.

### Task 5 — Traction memory and notification dedupe

**Files:** `desktop/ui/traction.mjs`, `desktop/ui/storage.mjs`, `desktop/tests/traction.test.mjs`.

**Interfaces:** `compareSnapshots(previous,current)` and `createPreferencesStore(storage)`.

- [ ] Step 1: Tests for two timestamps, zero denominators, mismatched pool/provider, duplicate event key, watchlist persistence.
- [ ] Step 2: Run tests; confirm RED.
- [ ] Step 3: Implement modest local history in MVP; add SQLite only in separately verified Milestone B.
- [ ] Step 4: Run tests; confirm GREEN.
- [ ] Step 5: Commit `feat(mika): recheck snapshots and persist watch preferences`.

### Task 6 — Responsive MIKA companion interface

**Files:** `desktop/ui/index.html`, `desktop/ui/styles.css`, `desktop/ui/app.mjs`, `desktop/ui/assets/`.

**Interfaces:** `render(state)`, `setCharacterState(state)`, `scanToken(address)`.

- [ ] Step 1: Manual wireframe and reduced-motion review; ensure sidebar remains usable at 390px.
- [ ] Step 2: Build Scan / Traction / Watch / Ask MIKA navigation with actual controller bindings (no synthetic tokens).
- [ ] Step 3: Build idle / scanning / warning / activity transitions with static fallback.
- [ ] Step 4: Verify empty, delayed, connected and offline states; basic keyboard navigation.
- [ ] Step 5: Commit `feat(mika): add animated research sidecar UI`.

### Task 7 — Acceptance and release gate

**Files:** `README.md`, `desktop/.github/workflows/ci.yml` (or repository workflow after migration), `desktop/tests/`.

- [ ] Step 1: Run `node --test desktop/tests/*.test.mjs`; tests pass.
- [ ] Step 2: Run `cargo check` and `cargo test` in `desktop/src-tauri`.
- [ ] Step 3: On Windows, run Tauri dev/build and verify the 390px sidecar, tray, persistent settings and error states.
- [ ] Step 4: Confirm JARVIS/DIT main branches and databases unchanged, no wallet/trade API, no fake green safety status.
- [ ] Step 5: Commit release notes with an honest list of passing checks and remaining blockers.

## Execution sequence

The first working increment is Tasks 1–4 + minimal Task 6; Tasks 5 and 7 follow within the prototype. Full wallet attribution, independent Solana RPC verification, production-aligned animation, Supabase sync and offline SQLite history are separate milestones requiring additional verified work. Never treat the one-hour target as proof all milestones shipped.

## Release and repository migration

Current GitHub app does not expose repository creation. Work is staged in `reixdd/1` on `mika-isolated-project`, under `mika/`. Do not merge into JARVIS `main`. When the user creates `reixdd/mika`, migrate the subtree to the new repository's root, verify assets/licenses, then publish a proper PR and release.
