# MIKA v0.4 — Creator Evidence, Launch History and Moderated Community Reports (Design)

**Date:** 2026-10-18
**Status:** Written specification for user review. No public reputation service is live.
**Dependency:** Read-only `mika/docs/superpowers/specs/2026-10-18-mika-v04-evidence-radar-design.md` and a deployed authenticated feedback service; may be implemented independently after its own review.

## Intent

When MIKA inspects a newly launched Solana token, she should remember public on-chain evidence tied to its *verified creator address*, including repeated token creations, creator-associated token transfers, and observed selling activity. A user can submit a token-specific report with evidence, but one person's unverified accusation must not turn a wallet into a defamatory fraud label. All outputs are factual, time-stamped research observations, not trading recommendations.

## Options and recommendation

**Recommended:** Separate dedicated Supabase project or isolated backend and database schema for MIKA, with authenticated write APIs, private report staging, moderator review, and a read-only public evidence projection. Keep creator identity evidence sourced from an indexing provider or verified on-chain transactions, not token names. Core MIKA and DIT remain untouched.

**Alternative:** Local-only SQLite for prototype; least risky but reports cannot be shared publicly. Use as offline cache and first integration fixture, not as purported worldwide reputation.

**Rejected:** Unmoderated public complaint feed, auto-blacklisting by ticker, or storing third-party accusations directly in tokens table. These are high-risk for false attribution and manipulation.

## Identity model

- Token identity = `sol:<case-sensitive_base58_mint>`.
- Creator identity = verified `sol:<case-sensitive_creator_pubkey>`; may be null.
- Relationship `CREATED_BY` requires the decoded on-chain Pump create event/account or trusted named provider with verifiable transaction signature, instruction/program version and slot. Do not infer creator from logo, Telegram/X, deploy funding address, or claim the wallet is a specific real person.
- A launch can have *multiple relevant roles*: token creator, fee recipient, creation signer, authority, funder. Store each independently, not all as "dev wallet."
- Wallet transfer, token sale, creator token balance, shared funding and temporal correlation are separate facts. Common ownership is **not** established merely by correlated buys or same funding source.
- Pump program version and migration state must be preserved. Creator reassignment and fee-sharing config can change reported creator role.

## Data contracts

### `creator_evidence`
`id` UUID, `mint` Solana address, `creator_pubkey` Solana address or null, `role`, `source`, `signature` or null, `slot` or null, `observed_at` UTC, `evidence_level` = `ONCHAIN_VERIFIED|PROVIDER_REPORTED|HEURISTIC|UNKNOWN`, `method` = provider/protocol-specific decoder name, `raw_reference` validated nonsecret URL, `last_rechecked_at`.

### `launches`
`mint`, `creator_pubkey` nullable, `created_at`, `evidence_id`, `launchpad`, `market_status`, `last_seen_at`. Multiple launches from one creator may be counted only when creator identity is sufficiently supported.

### `creator_market_events`
`mint`, `actor_pubkey`, `role`, `event_type` = `TOKEN_TRANSFER|TOKEN_SALE|LIQUIDITY_CHANGE|CREATOR_BALANCE`, `signature`, `slot`, `amount_raw`, `token_decimals`, `quote_amount_nullable`, `source`, `observed_at`. Sale requires a decoded trade not just transfer; liquidity movement requires identified pool activity.

### `feedback_reports` (private write-side)
`id`, `reporter_user_id`, `mint`, `creator_pubkey` nullable, `category`, `statement` max 600 chars, `evidence_links` up to 3 validated Solana explorer / provider links, `submitted_at`, `status` = `PENDING|APPROVED|REJECTED|WITHDRAWN`, `moderator_id`, `reviewed_at`, `moderation_reason`.
Never expose reporter IDs, private notes, IP addresses, or moderation credentials publicly.

### Public projection
`token_creator_summary`: number of *verified* launches for known creator, date range, observed market/transfer indicators with evidence references, last checked time, independent unknowns, and approved feedback count (not "scam votes"). Show no percentage "rug rate" unless a validated denominator and objective outcome definition exist.

## Feedback restrictions and moderation

- Users must authenticate before submitting feedback. Verify challenge/CSRF/session and per-user/global rate limits. No anonymous public abuse mechanism in initial release.
- Accept strictly bounded factual, token-specific observations with at least one checkable public transaction/source. Clear banner: public reports are user statements, not verified findings. Never ask for personal identity, contact details or private wallet credentials.
- Pending reports remain **private** and never automatically change the creator summary, visibility filters or risk verdict. Manual reviewer approval plus evidence validation is required.
- Reject threats, identifying personal information, personal harassment, unverifiable claims about individuals, spam and duplicate reports. Moderators may hide or remove published reports; maintain audit trail, evidence expiry and appeal/correction route.
- Public display prefers neutral categories such as `REPORTED_CONCERN` with an evidence link over labels like `SCAMMER` or `RUGGER`.
- Community reports do not determine HIGH RISK without corroborated objective evidence.
- Publish a clear privacy notice, retention limits and data correction process before opening feedback to the public.

## Collection and rechecking

- MIKA initially imports creator evidence from GMGN provider responses when explicit. Mark it `PROVIDER_REPORTED` and retain raw field + source timestamp.
- For on-chain verification use Solana RPC and appropriately licensed logs/indexers; decode Pump Create events (v1/v2) and applicable migration-related changes. Always preserve signature and decoder version. Historical backfill may be incomplete; display coverage limits.
- Do not infer creator identity from launch ticker or lookalike logos. Same creator wallet launching multiple tokens is a public chain-level relationship, not proof of malicious intent.
- Recheck creator summaries daily while observed, and when a new token references a known creator. Deduplicate by chain+signature+event_kind; backoff on rate limits.
- Store a negative lookup only as `unresolved` with expiry, not as proof a creator has zero past launches.
- Deletion and correction must invalidate cached public summaries.

## User experience

- A token card expands to show `CREATOR HISTORY` section: verified on-chain creator address with one-tap copy, count of known prior launches and the oldest/newest dates, provider coverage note, and observed sales/transfer changes with links. If no verified creator: `Creator identity unverified`.
- Separate `Community evidence` section in token detail panel only: approved reports count, source references, submit feedback after authentication. No permanent "bad dev" tag on an unverified accusation.
- Tiny MIKA synopsis distinguishes direct on-chain facts, provider reports, observations, and unknowns, capped at two sentences without buy/sell endorsements.
- Public website may query the read-only projection, not private feedback row tables.
- The desktop remains usable offline with cached public evidence and clear last-verified timestamps.

## Storage, permissions and security

- Use a dedicated project/schema that does not share DIT treasury, worker, wallet or operator data. Supabase can provide authentication, RLS and moderation APIs when enabled.
- RLS: submitter can create/read their own private pending report; only moderator role can update review status; public anonymous read only from sanitized approved projection.
- Moderation write API never trusts client-supplied reviewer/user ID or status.
- Do not expose Supabase service role secret or JARVIS/Ollama local host to website visitors.
- Per-device cache and cloud projection distinguish data-collection time from retrieval time.
- Public rollout remains OFF pending account configuration, security validation and abuse policy review.

## Acceptance tests

1. Two different token mints with the same verified creator signature/role appear in creator history; matched ticker but different creator does not.
2. A funding wallet or social account cannot be silently promoted to creator identity.
3. Transfer and on-chain sale are distinct classes; no "dev sold" if only transfer evidence exists.
4. GMGN-provided address with no verified transaction is visibly provider reported.
5. Missing or stale creator index shows unknown, not zero historic launches.
6. Unreviewed feedback stays private and cannot influence a public risk label or filter.
7. Approvals are restricted to an authenticated moderator and auditable; client cannot self-approve.
8. Reporter identity, text containing personal data and unapproved statements never escape to public projection.
9. A corrected/withdrawn report vanishes from public summary after cache invalidation.
10. Load/abuse tests for duplicate submissions, identity forgery, race on moderation status and deleted report retention pass before deploy.

## Release phases

- A: Desktop-local creator evidence cache and read-only creator detail presentation (can be shipped without Supabase feedback).
- B: Independent moderated feedback backend with protected reporting and approved public projection.
- C: Website evidence view, production RLS/CSRF/rate-limit audit, removal/correction policy, opt-in deploy.
- D: Backfill evaluation and on-chain decoder accuracy tests; report coverage and uncertainties.

No real-funds, trading, automatic purchase, wallet connection or private-key functionality.
