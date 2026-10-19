# MIKA v0.4 Creator Evidence and Community Moderation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give MIKA a verifiable memory of Solana token creator roles, prior launches and observed chain activity, with optional authenticated, moderated community reports that never automatically label wallets or individuals as scammers.

**Architecture:** A pure evidence model consumes provider and decoded on-chain claims, keyed by mint/signature/role; an isolated local cache stores facts independently of JARVIS and DIT. A separately provisioned, authenticated Supabase project or backend provides private feedback submissions, manual moderation and a sanitized public projection. No public-feedback rollout until access-control, abuse tests and owner deployment verification pass.

**Tech Stack:** Existing vanilla JS ES modules / Node test runner / Tauri desktop, Solana RPC read-only verification, optional Supabase Postgres + Auth + Row Level Security + Edge Function review endpoints.

**Spec:** `mika/docs/superpowers/specs/2026-10-18-mika-v04-creator-evidence-and-community-design.md`

## Global Constraints

- Implement **after** Evidence Radar Tasks 1–5 are stable; creator history must never block Pump.fun research scanning.
- No association with individual human identities: keys are case-sensitive public Solana mint/creator addresses only.
- `creator` is not a synonym for signer, fee recipient, pool deployer or funding wallet. Preserve role and decoder provenance.
- "Creator sold" requires a verified parsed sale; generic token transfers and price declines are not proof.
- Null or expired creator index means unknown, **never** zero historical launches.
- A shared funding wallet, coordinated early trades or high bundler ratio are **risk clues**, not proof one person controls multiple wallets.
- Community reports require authenticated reporter, verifiable public links, moderator review and reversible/appealable decisions. Unmoderated reports must not appear in public output or change a security verdict.
- Strict isolation: don't write to DIT treasury, worker, agent or wallet tables, JARVIS main/data, or any unrelated external project.
- Public backend / anonymous report submission remains OFF until separate owner credential provisioning, security tests, and live deployment confirmation.

## Review Focus

1. **Lookalike tickers:** same ticker + different verified creator must not be grouped together (Task 1).
2. **Unverified creator roles:** `funder` / `feeRecipient` cannot be silently promoted to `creator` (Task 1).
3. **Replayed or duplicated signatures:** repeat indexing must not double-count creator launches or transfers (Task 2).
4. **Report abuse:** anyone cannot submit or approve on behalf of a different user; pending content cannot leak (Tasks 4–5).
5. **Corrections/withdrawals:** public projection and cache invalidation must stop displaying removed feedback without deleting the audit trail (Task 5).

---

### Task 1: Typed creator identity and event normalization

**Files:**
- Create: `mika/desktop/ui/creator-evidence.mjs`
- Test: `mika/desktop/tests/creator-evidence-v04.test.mjs`

**Interfaces:**
- `normalizeCreatorClaim(raw, {mint,source,observedAt}): CreatorEvidence|null`
- `classifyCreatorRole(raw): 'CREATOR'|'FEE_RECIPIENT'|'SIGNER'|'FUNDER'|'AUTHORITY'|'UNKNOWN'`
- `normalizeCreatorEvent(raw): CreatorMarketEvent|null`
- `summarizeCreatorHistory(launches,events,creator): CreatorSummary` with coverage and unknowns.

- [ ] Step 1: Write tests for verified create role, provider-only role, separate signer/funder identity, same creator two mints, same symbol different creator, transfer not sale, null creator and stale coverage.
- [ ] Step 2: Run `cd mika/desktop && node --test tests/creator-evidence-v04.test.mjs`; ensure RED from missing exports.
- [ ] Step 3: Implement normalization without inventing creator identity. Require signature+role+decoder evidence before marking ONCHAIN_VERIFIED; otherwise retain PROVIDER_REPORTED or UNKNOWN.
- [ ] Step 4: Re-run targeted and full desktop tests; require 0 failures.
- [ ] Step 5: Commit `feat(mika): normalize creator roles with evidence provenance`.

### Task 2: Local launch-history cache and transparent coverage

**Files:**
- Create: `mika/desktop/ui/creator-cache.mjs`
- Modify: `mika/desktop/ui/storage.mjs`
- Test: `mika/desktop/tests/creator-cache-v04.test.mjs`

**Interfaces:**
- `createCreatorCache(storage,{now,ttlMs=86400000}): {saveEvidence,getCreator,launchesFor,expire}`
- Dedupe key: `sol:<mint>:<role>:<signature-or-provider-evidence-id>`. `creator_pubkey` indexed separately.

- [ ] Step 1: Test 2 verified mints aggregate; duplicate event doesn't; role conflict is preserved; stale/unknown not displayed as zero; migration preserves existing `watched[]` and `tokenMeta`.
- [ ] Step 2: Run `node --test tests/creator-cache-v04.test.mjs`; require RED.
- [ ] Step 3: Implement bounded local creator-history cache independent of market snapshot storage. Enforce caps/expiry and source timestamps; don't run unbounded on-chain backfills.
- [ ] Step 4: Run targeted and full tests.
- [ ] Step 5: Commit `feat(mika): retain separate local creator history cache`.

### Task 3: Read-only on-chain verification and local UI

**Files:**
- Create: `mika/desktop/ui/creator-provider.mjs`, `mika/desktop/ui/creator-view.mjs`
- Modify: `mika/desktop/src-tauri/src/main.rs`, `mika/desktop/ui/data.mjs`, `mika/desktop/ui/app.mjs`
- Test: `mika/desktop/tests/creator-provider-v04.test.mjs`; Rust allowlist tests in `main.rs`.

**Interfaces:**
- `createCreatorProvider({fetchVerifiedCreation,fetchCachedEvidence}): {inspectMint(mint),inspectCreator(pubkey)}`
- `renderCreatorSection(summary,{onCopy,onOpenEvidence}): DocumentFragment` shown in token details, not mandatory for all rolling rows.

- [ ] Step 1: Test fixed-mint allowlist, 404/timeout, no generic arbitrary RPC passthrough, provider-vs-chain verification, repeated launches, and protected unknowns. Confirm RED.
- [ ] Step 2: Implement constrained read-only adapter to selected Solana RPC/indexer functionality. No user-provided URL or arbitrary program instruction. Require a known decoder, program ID, transaction signature, slot and creator role before classing as on-chain verified.
- [ ] Step 3: Render compact Creator History: known creator address + Copy, prior *verified* launches count with coverage, recent verified market events and source links; unknown when absent.
- [ ] Step 4: Run targeted and full JS tests; Windows CI checks for Rust/native bridge.
- [ ] Step 5: Commit `feat(mika): inspect verified creator history without identity guesses`.

### Task 4: Independent feedback schema with authenticated write path

**Files:**
- Create: `mika/community/migrations/001_creator_reports.sql`, `mika/community/report-validation.mjs`, `mika/community/submit-report.mjs`, `mika/community/package.json`
- Test: `mika/community/tests/validation.test.mjs`, `mika/community/tests/policy.test.mjs`.

**Interfaces:**
- `validateReport(input): {mint,category,statement,evidenceLinks}|ValidationError`
- `submitReport(authenticatedUserId,input,repository): PendingReport`
- Storage table `feedback_reports` private by default; `reporter_user_id` comes from verified session **only**.

- [ ] Step 1: Test 600-character cap, one required transaction/provider evidence link, up to 3 links, bad/private URLs, invalid mint, spoofed reporter and missing auth; expect RED.
- [ ] Step 2: Write dedicated MIKA project migration with authenticated submitter-only insert/read and moderator-only update policies; no unqualified `public` anonymous table reads.
- [ ] Step 3: Implement submission guard, typed statuses `PENDING|APPROVED|REJECTED|WITHDRAWN`, duplicate suppression and per-user limits.
- [ ] Step 4: Run Node tests and SQL policy checks in a **disposable test project**. If separate Supabase project is not provisioned, mark integration blocked instead of applying migration to DIT.
- [ ] Step 5: Commit `feat(mika): stage private authenticated feedback intake`.

### Task 5: Manual review and sanitized public projection

**Files:**
- Create: `mika/community/review-report.mjs`, `mika/community/public-summary.mjs`, `mika/community/tests/moderation.test.mjs`
- Modify: `mika/community/migrations/001_creator_reports.sql`
- Test: `mika/community/tests/moderation.test.mjs`

**Interfaces:**
- `moderateReport(moderatorClaims,reportId,decision,reason): ModerationEvent`
- `publicCreatorSummary(creator,approvedReports,evidence): SanitizedCreatorSummary`
- `withdrawReport(userClaims,reportId): WithdrawalEvent` revokes public visibility with cache invalidation.

- [ ] Step 1: Tests reject reporter self-approval, leaked private notes/report IDs, anonymous reads of pending reports, duplicate approvals and published withdrawn reports; run RED.
- [ ] Step 2: Implement moderator-only approval/reject/withdraw with private audit trail, no automatic "scammer" classification, and public summary of evidence-backed concern count with links.
- [ ] Step 3: Add correction/withdrawal invalidation; test RLS/authorization in separate disposable environment.
- [ ] Step 4: Run all community tests and inspect produced projection for private-field leakage.
- [ ] Step 5: Commit `feat(mika): enforce moderated evidence projection`.

### Task 6: Community feedback UI and optional sync

**Files:**
- Create: `mika/desktop/ui/community-feedback.mjs`, `mika/web/community-transport.mjs`
- Modify: `mika/desktop/ui/app.mjs`, `mika/web/app.mjs`
- Test: `mika/desktop/tests/community-feedback-v04.test.mjs`, `mika/web/tests/community-transport-v04.test.mjs`

**Interfaces:**
- `renderCommunityEvidence(summary,viewerAuth): HTMLElement` displays APPROVED only, source references and clear moderation caveat.
- `submitFeedback(report,auth): Promise<PendingStatus>` explicit authenticated opt-in, never background upload.
- Local desktop works with empty/unavailable report backend.

- [ ] Step 1: Tests for logged-out submission rejection, online pending confirmation, absent backend, only approved neutral report display, no actor inference from a social handle; require RED.
- [ ] Step 2: Add modest Creator History/Community Evidence disclosures in token detail only. Keep existing Scan/Traction/Watch performance independent of cloud response.
- [ ] Step 3: Run JS suites for desktop/web/community and confirm the feature is not accessible without a configured authenticated backend.
- [ ] Step 4: Commit `feat(mika): display verified creator memory and moderated feedback`.

### Task 7: Security, privacy and staged release gate

**Files:**
- Modify: `mika/community/README.md`, `mika/VALIDATION.md`, `mika/docs/superpowers/progress-v04.md`
- Test: security/abuse regressions above + Windows GitHub Actions.

- [ ] Step 1: Verify no new database tables are created in DIT; separately inspect target project ID before any migration. Retain public-feedback OFF flag.
- [ ] Step 2: Run `npm test` in desktop, web, cloud, connector and community; record exact counts. Run Windows Tauri build and compare JARVIS/DIT branch state.
- [ ] Step 3: Test unauthorized moderation, forged creator linkage, replayed transactions, large feedback burst, withdrawal/correction, RLS and privacy leaks on the disposable environment.
- [ ] Step 4: Verify that each displayed known-creator link resolves to the underlying public evidence and that no community claim affects deterministic risk without corroboration.
- [ ] Step 5: Publish **only a source/preview candidate** until owner provisions separate Supabase project, credentials and deployment controls; do not turn on anonymous reporting or claim public reputation live.
- [ ] Step 6: Commit `chore(mika): validate creator memory and moderated-feedback preview`.

## Delivery Notes

The creator identity module and local cache (Tasks 1–3) can ship in MIKA without cloud moderation, and should be verified independently. The moderation backend (Tasks 4–7) needs a dedicated isolated provider project, authenticated reviewer, and a reversible public-report policy. Never treat a partial hosted site or automatically generated AI narrative as proof a creator committed fraud.
