# MIKA v0.4 Evidence Radar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a testable Windows MIKA research sidecar with complete *source-attributed* GMGN launch-risk display, verified deep links, adjustable market research filters, three tabs, and optional accent personalization.

**Architecture:** Keep the existing JARVIS read-only HTTP bridge, GMGN launch feed, DEX quote polling and Tauri shell. Add a typed evidence projection separate from market observations; hydrate a bounded subset of selected, watched and currently visible tokens using allowlisted JARVIS GET routes. UI sorting/filtering works on these immutable normalized records, not on fabricated values or LLM verdicts.

**Tech Stack:** Tauri 2, existing Rust native bridge, vanilla JS ES modules, Node built-in test runner, Windows GitHub Actions.

**Spec:** `mika/docs/superpowers/specs/2026-10-18-mika-v04-evidence-radar-design.md` (includes low-priority approved personalization addendum).

## Global Constraints

- Branch from `mika-v04-evidence-and-creator-memory-design` to a new isolated implementation branch. Do **not** merge into `reixdd/1` main or edit DIT.
- Research only. No wallet, swaps, orders, private keys, automatic trades or guaranteed profitability claims.
- Solana base58 mint addresses preserve exact case and are the only token identity; pool metrics retain distinct pool keys.
- GMGN ratios are 0–1 if valid, unknown otherwise; null is **not** zero. Persist raw, source, original observation time and response family.
- Default Traction filters: market cap strictly < $30,000; bundler rate strictly < 0.30. Unverified is a separate visible count/category; absent evidence must never silently pass.
- Existing 5m buy/sell bar represents **transaction counts**, not trading USD or unique wallets. Market-cap bars are relative visualization only.
- Keep the desktop view responsive at 390–420px; no aggressive 1-second **security** polling.
- Public creator-memory work is in a separate plan; it must not block this release.
- Personalization comes **last**, only after data, security evidence, and display tests pass.

## Review Focus

1. **Valid zero** `bundler_trader_amount_rate:0` and `top_10_holder_rate:0` must render "0%" with GMGN and timestamp rather than "unknown" (Task 1).
2. **Nested API wrappers** `{security:{ok:true,data:{data:{...}}}}`, failed source and out-of-range raw percentages must be distinguished; no false safety label (Tasks 1–2).
3. **Transient upstream 429/timeout and old cache** must preserve prior evidence timestamp and show delayed/unavailable without re-stamping it as fresh (Task 2).
4. **Unknown bundler ratio** with $12k market cap must not pass the 30% filter; it belongs in Unverified (Task 3).
5. **Broken or deceptive social URLs and historical watchlist prefs** must be rejected/migrated without losing saved mints (Tasks 4 and 6).

---

### Task 1: Normalize GMGN launch and per-token security evidence

**Files:**
- Modify: `mika/desktop/ui/live-feed.mjs`, `mika/desktop/ui/risk.mjs`, `mika/desktop/ui/domain.mjs`
- Create: `mika/desktop/ui/security-evidence.mjs`
- Test: `mika/desktop/tests/security-evidence-v04.test.mjs`

**Interfaces:**
- `projectLaunchEvidence(raw, {source, observedAt}): {metrics, unknowns, provenance}`
- `projectTokenEvidence(bundle, {observedAt}): {metrics, unknowns, provenance}`
- `mergeEvidence(launchEvidence, tokenEvidence): {metrics, provenance, conflicts, unknowns}`
- `formatRatio(ratio): string` returns e.g. `"0%"`, `"28%"`, or `"Unknown"`.

- [ ] Step 1: Write tests for zero, 0.28, 0.31, missing, 30 (ambiguous units), nested wrappers, failed `ok:false`, disagreeing source values, and separate observed timestamps.
- [ ] Step 2: Run `cd mika/desktop && node --test tests/security-evidence-v04.test.mjs`; confirm RED because new exports do not exist.
- [ ] Step 3: Implement the four interfaces in `security-evidence.mjs` and use them from existing feed and risk normalizers. Preserve unknown raw values without guessing percentage units.
- [ ] Step 4: Re-run targeted test then `npm test`; require 0 failures.
- [ ] Step 5: Commit `feat(mika): preserve attributable GMGN evidence and explicit zeros`.

### Task 2: Bounded security enrichment without market quote overload

**Files:**
- Create: `mika/desktop/ui/security-cache.mjs`
- Modify: `mika/desktop/ui/data.mjs`, `mika/desktop/ui/app.mjs`
- Test: `mika/desktop/tests/security-cache-v04.test.mjs`

**Interfaces:**
- `createSecurityCache({getToken,clock,concurrency=2,ttlMs=60000}): {get(mint),peek(mint),status(mint)}`
- `getToken(mint)` calls existing `client.token('sol',mint)` read-only; `/api/operator/gmgn/token` is **not** a new arbitrary URL.
- `peek(mint)` yields saved evidence plus original `observedAt`, never fetch timestamp disguised as observation.

- [ ] Step 1: Test two simultaneous enrichments, third queued; 60-second cache, 429 backoff, stale cached return and an unknown-mint 404 fallback.
- [ ] Step 2: Run `node --test tests/security-cache-v04.test.mjs` for expected RED.
- [ ] Step 3: Implement bounded cache and attach to selected/Watch and top visible Traction/Scan rows only; do not poll each visible token once per second. Error states source-labeled.
- [ ] Step 4: Run targeted and full `npm test`; require 0 failures.
- [ ] Step 5: Commit `feat(mika): hydrate selected token security with bounded GMGN requests`.

### Task 3: Evidence-based research filters and ranking

**Files:**
- Create: `mika/desktop/ui/research-filter.mjs`
- Modify: `mika/desktop/ui/traction.mjs`
- Test: `mika/desktop/tests/research-filter-v04.test.mjs`

**Interfaces:**
- `classifyCandidate(record, {maxMarketCap=30000,maxBundlerRatio=0.30,enableCap=true,enableBundler=true}): 'WITHIN'|'OUTSIDE'|'UNVERIFIED'`
- `partitionCandidates(rows, filters): {within,outside,unverified}`
- `sortCandidates(rows, sort): rows` where `sort` is `recent|volume5m|buySellImbalance|marketCap`.

- [ ] Step 1: Test boundaries 29,999/30,000; 0/0.2999/0.30; unknown ratio; non-finite market cap; disabled filters; sorting ties by deterministic mint and timestamp.
- [ ] Step 2: Run `node --test tests/research-filter-v04.test.mjs`; require RED.
- [ ] Step 3: Implement pure functions with no network or model calls. Partition `UNVERIFIED` separately; high 5m volume must never override an outside/unknown risk gate.
- [ ] Step 4: Run targeted and full `npm test`; require GREEN.
- [ ] Step 5: Commit `feat(mika): add transparent configurable research filters`.

### Task 4: Safe GMGN and source-provided X links

**Files:**
- Create: `mika/desktop/ui/token-links.mjs`
- Modify: `mika/desktop/ui/token-media.mjs`, `mika/desktop/ui/live-feed.mjs`, `mika/desktop/ui/app.mjs`
- Test: `mika/desktop/tests/token-links-v04.test.mjs`

**Interfaces:**
- `gmgnTokenUrl(mint): 'https://gmgn.ai/sol/token/<mint>'|null` with exact validated base58.
- `sourceXUrl(sourceRow): string|null` accepts explicit provider `socials[]`, `twitter`, `twitter_url` or valid `twitter_username`; no synthesized ticker username.
- `buildTokenLinks(row): {gmgn,x,chart}` returning sanitized explicit sources.

- [ ] Step 1: Test exact case preservation, valid GMGN path, invalid 1/escape mint, accepted X handle, lookalike `x.com.evil`, `javascript:`, nonexistent socials, and blank chart.
- [ ] Step 2: Run `node --test tests/token-links-v04.test.mjs`; confirm RED.
- [ ] Step 3: Implement URL helpers and wire Scan, Traction, detail and Watch action rows. Open external links with `noopener noreferrer`.
- [ ] Step 4: Run tests and inspect exact rendered link label/content.
- [ ] Step 5: Commit `feat(mika): add trustworthy GMGN and social deep links`.

### Task 5: Three-tab UI, filtering and factual synopsis

**Files:**
- Modify: `mika/desktop/ui/index.html`, `mika/desktop/ui/app.mjs`, `mika/desktop/ui/styles.css`
- Create: `mika/desktop/ui/research-summary.mjs`
- Test: `mika/desktop/tests/three-tabs-v04.test.mjs`

**Interfaces:**
- `summarizeTokenEvidence(record,evidence): {headline,detail,unknowns,observedAt}`; deterministic, capped 2 sentences.
- `setTractionFilters(filters)` uses Task 3 partition and saved settings; tabs `scan|traction|watch` only.
- `renderResearchSummary(...)` uses real evidence with a neutral default.

- [ ] Step 1: Test missing security => "Unverified" and specific unknowns, provider zero 0% displayed, conflict note, two-sentence cap, and exactly three rendered tabs with no `view-ask`/chat form/model picker.
- [ ] Step 2: Run `node --test tests/three-tabs-v04.test.mjs`; confirm RED.
- [ ] Step 3: Replace event-wall / vague synopsis with compact token-first summaries, filter controls and within/outside/unverified counts. Remove Ask UI bindings, not the separate dormant Ollama native command used by potential website connector.
- [ ] Step 4: Run full desktop unit suite; check keyboard focus and screenshot at 390px and 420px Windows sizes. Existing Watch and market quote refresh must still work.
- [ ] Step 5: Commit `feat(mika): render evidence-first three-tab radar`.

### Task 6: Low-priority accent and display preferences

**Files:**
- Modify: `mika/desktop/ui/storage.mjs`, `mika/desktop/ui/index.html`, `mika/desktop/ui/styles.css`, `mika/desktop/ui/app.mjs`
- Create: `mika/desktop/ui/theme.mjs`
- Test: `mika/desktop/tests/theme-v04.test.mjs`

**Interfaces:**
- `normalizeAccent(value): {name,hex}|null` accepts fixed `violet|mint|ice|white|rose|amber` or strict `^#[A-Fa-f0-9]{6}$`.
- `migratePreferences(old): preferences` preserves all existing watched mints, quote settings and previous avatar/motion choices.
- `applyAccent(element,accent):void` sets only scoped CSS custom properties for decorative accents; not semantic warning colors.

- [ ] Step 1: Test preset switch, custom `#A78BFA`, malicious CSS `url(...)`, invalid hex, persistence across restart, old watchlist migration, reduced motion and compact density.
- [ ] Step 2: Run `node --test tests/theme-v04.test.mjs`; verify RED.
- [ ] Step 3: Add small Settings controls and scoped accents. Do **not** expand UI into a settings dashboard.
- [ ] Step 4: Run full suite and small-screen manual verification; require no regressions.
- [ ] Step 5: Commit `feat(mika): add compact accent personalization`.

### Task 7: Verification and versioned Windows candidate

**Files:**
- Modify: `mika/README.md`, `mika/VALIDATION.md`, `mika/desktop/package.json`, `mika/desktop/src-tauri/tauri.conf.json`, `mika/desktop/src-tauri/Cargo.toml`
- Check: existing `.github/workflows/mika-windows.yml`.

- [ ] Step 1: Run `cd mika/desktop && npm test`, `cd ../web && npm test`, `cd ../cloud && npm test`, `cd ../connector && npm test` and record exact counts. Verify no change to remote Ask website contract.
- [ ] Step 2: Run Windows GitHub Actions CI from isolated implementation branch; Rust/Tauri build and artifact must both succeed. No local Rust verification claimed unless actually run.
- [ ] Step 3: In the installed app, verify a genuine GMGN low/zero bundler token, a missing-data token, a high bundler token, X and GMGN navigation, 3 tabs, exact CA copy, preferences and quote timestamps.
- [ ] Step 4: Check source diff for no wallet, swaps, secrets, changes to JARVIS main or DIT; check license/privacy handling for provider data.
- [ ] Step 5: Only after checks pass, bump to `0.4.0-rc1`, build installer and document unverified live provider conditions. Commit `chore(mika): validate evidence radar release candidate`.

## Execution sequencing

Tasks 1–5 are the **performance and trust-critical** path. Task 6 is cosmetic and may be omitted from the first candidate if time is constrained. Task 7 requires passing native Windows CI; no installer link is valid until an actual downloaded artifact is verified. Creator history/community feedback has its own spec and plan; don't fold that infrastructure into this hotfix.
