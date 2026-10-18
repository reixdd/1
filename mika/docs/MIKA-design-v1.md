# MIKA — Technical Design Specification
**Version:** 1.0  
**Date:** October 18, 2026  
**Status:** Proposed — awaiting specification approval  
**Platform:** Windows 11, Solana-first, research-only

## 1. Product definition

MIKA (Market Intelligence & Knowledge Assistant) is an independent desktop AI companion designed to run beside GMGN Trenches.

Her purpose is to investigate token launches, explain available on-chain evidence, identify suspicious activity, and track changes in previously observed tokens.

MIKA must never claim that a speculative token is guaranteed safe or profitable. She does not connect wallets, execute transactions, place orders, or manage real funds.

**Core experience:** Open MIKA, inspect a new token, see the supporting and contradictory evidence, save it for observation, and receive useful updates when its market or risk profile changes.

## 2. Architecture decision

### Selected: Separate Tauri application + existing JARVIS core

MIKA will be developed as a separate project, provisionally `reixdd/mika`, without modifying JARVIS's existing architecture.

The runtime will have four layers:

| Layer | Responsibility |
|---|---|
| JARVIS Core | Canonical market discovery, observations, Quant, graph, evidence and research |
| MIKA Data Adapter | Read-only API calls, normalization, validation and freshness |
| MIKA Intelligence | Deterministic risk rules, historical comparisons and explanations |
| MIKA Desktop | Character, token details, interaction, settings and notifications |

MIKA will not create another independent market scanner or write to JARVIS's operational database.

### Alternatives rejected

**Browser extension:** Easier access to the currently displayed token but introduces website-DOM dependencies, permissions and breakage when GMGN changes its interface.

**Completely independent scanner:** Offers greater autonomy but duplicates JARVIS's provider polling, storage, research logic and maintenance.

**Decision:** Use the standalone desktop companion first. Explicit token selection is supported immediately; automated browser-context integration requires a separately reviewed feature.

## 3. Existing JARVIS API integration

Default development origin: `http://127.0.0.1:8768`.

| Existing endpoint | MIKA usage |
|---|---|
| `GET /health` | Core connectivity |
| `GET /api/operator/radar` | Canonical active and watched markets |
| `GET /api/operator/dossier` | Token market, Quant, risk, graph, history and synthesis |
| `GET /api/operator/gmgn/status` | GMGN availability and configuration |
| `GET /api/operator/gmgn/trenches` | GMGN new-creation research |
| `GET /api/operator/gmgn/token` | GMGN token details and optional holder evidence |
| `GET /api/operator/chart` | Historical local chart |
| `GET /api/attention` | Existing meaningful research events |
| `GET /api/models` | Available local models |

The initial MIKA client will not call JARVIS's mutation endpoints. Its watchlist and customization settings are maintained separately.

### Important compatibility rules

The current GMGN Trenches bridge requests the `new_creation` category. An extension is required before MIKA can request additional lifecycle categories or server-side filters.

The current dossier endpoint returns HTTP 404 when the token does not exist in JARVIS's canonical universe. MIKA must then display available direct GMGN evidence separately and label missing canonical history as unavailable.

Existing JARVIS risk polling currently supports selected EVM chains via GoPlus; this must not be represented as comprehensive Solana risk coverage.

## 4. Source ownership

**GMGN:** Primary provider-reported token analytics and launch-screening indicators.

**GeckoTerminal:** Existing JARVIS new-pool discovery and supplemental market activity.

**DEX Screener:** Market reconciliation, liquidity, pair data and token artwork where available.

**Solana RPC:** Independent on-chain verification when the Solana verifier is implemented.

**Ollama:** Optional natural-language interpretation, never the sole authority behind a security verdict.

Each result must retain its provider name, observation timestamp, collection status, and supported source reference.

Unknown or missing data remains null.

## 5. Canonical token identity

MIKA will distinguish two keys:

- `token_key`: `sol:<mint_address>`
- `market_key`: `sol:<mint_address>:<pool_address>`

A token can have multiple pools. MIKA groups observations under the token key but preserves pool-specific prices, liquidity, age and source evidence.

Ticker and project name are display metadata only. They are never unique identifiers.

If conflicting providers report materially different values, MIKA displays the source disagreement rather than silently choosing a favorable number.

## 6. Risk Evidence Engine

MIKA's risk system is deterministic. An AI model may explain the result, but cannot create or override verified evidence.

### Risk categories

| Category | Checks |
|---|---|
| Authority control | Mint authority, freeze authority, relevant Token-2022 extensions |
| Holder distribution | Concentration, ownership aggregation, supply exclusions |
| Creator exposure | Provider-reported creator holdings and verified related addresses |
| Launch coordination | Bundler indicators, unusually coordinated early activity |
| Trading integrity | Wash-trading claims, unusual buy/sell behavior |
| Liquidity | Current liquidity and observed material withdrawal |
| Provenance | Provider conflicts, stale data, missing critical checks |

### Evidence classification

Every finding must carry one of these classifications:

- `ONCHAIN_VERIFIED`: Confirmed directly from a specified on-chain account or transaction.
- `PROVIDER_REPORTED`: A third-party provider's claim, without independent confirmation.
- `HEURISTIC`: A pattern detected by MIKA's documented rules.
- `CONFLICTED`: Relevant sources disagree.
- `UNKNOWN`: The necessary evidence is not available.

This classification is independent of severity.

### Risk display states

**HIGH RISK:** Material concerns supported by sufficiently strong evidence.

**NEEDS REVIEW:** Suspicious or conflicting indicators that require further investigation.

**NO MAJOR FLAGS DETECTED:** Required checks completed without detecting the defined major warning conditions. This is not a safety guarantee.

**UNVERIFIED:** Critical checks missing, unavailable or too old.

No hidden numerical safety score will be shown.

Thresholds for concentration and provider-reported bundling must be configurable, documented and tested before being treated as meaningful indicators.

## 7. Traction Observation Engine

MIKA will periodically revisit tokens already in her observation set.

It compares successive timestamped observations instead of treating a single attractive snapshot as proof of momentum.

### Core features

| Feature | Interpretation |
|---|---|
| Five-minute volume | Change in reported trading activity |
| Buys and sells | Changes in transaction counts |
| Liquidity retention | Whether observed liquidity is maintained |
| Market-cap changes | Changes with source and time context |
| Participant activity | Unique participant evidence if supported |
| Wallet concentration | Whether activity or ownership appears unusually concentrated |
| Quant rank changes | Research ranking movement, not price prediction |

No metric is treated as proof of genuine organic demand by itself.

### Event labels

- `ACTIVITY_INCREASING`
- `ACTIVITY_WEAKENING`
- `LIQUIDITY_CHANGE`
- `CONCENTRATION_CONCERN`
- `RISK_EVIDENCE_CHANGED`
- `DATA_INCOMPLETE`

Each event includes the before and after timestamps, compared values, supporting sources and any uncertainty.

MIKA must use at least two temporally distinct observations for a change claim and avoid dividing by zero or comparing incompatible providers without disclosure.

Notifications are deduplicated and rate-limited to prevent repetitive alerts.

## 8. MIKA's normalized data contract

The interface consumes one consolidated `TokenDossier` model with these sections:

| Section | Required fields |
|---|---|
| Identity | `token_key`, `chain`, `mint`, `market_keys`, `symbol`, `name` |
| Market | `price`, `market_cap`, `liquidity`, `volume_5m`, `buys_5m`, `sells_5m` |
| Freshness | `observed_at`, `received_at`, `provider`, `status` |
| Security | `findings[]`, `severity`, `evidence_class`, `source`, `observed_at` |
| Traction | `events[]`, `previous_snapshot_at`, `current_snapshot_at` |
| Explanation | `summary`, `support[]`, `counter_evidence[]`, `unknowns[]` |

Each market or security value can be null, and null is never converted into zero unless zero was explicitly reported.

### Freshness policy

Proposed display thresholds for market observations:

- `FRESH`: Last observation no older than 45 seconds.
- `DELAYED`: Older than 45 seconds but no older than 180 seconds.
- `UNAVAILABLE`: No usable observation within 180 seconds.

These are MIKA UI freshness thresholds, not guarantees of exchange-level real-time prices. Security evidence may have a separately defined longer validity window.

## 9. Local persistence

MIKA will use its own app data directory, separate from JARVIS.

Target Windows location: `%LOCALAPPDATA%\MIKA\`.

Proposed SQLite database: `mika.sqlite`.

| Table | Purpose |
|---|---|
| `tokens` | Known token identities and display metadata |
| `market_snapshots` | Timestamped normalized market observations |
| `risk_evidence` | Source-attributed findings and uncertainty |
| `traction_events` | Meaningful detected changes |
| `watchlist` | User-selected tokens and notes |
| `preferences` | Character and interface settings |
| `notification_log` | Deduplication and notification history |

Keep observations linked to their exact token, source and timestamp. Store sufficient provenance to reconstruct why an alert appeared.

Historical retention and storage limits will be configurable. Old unpinned observations can be pruned without deleting the user's watchlist.

MIKA must not directly modify JARVIS's SQLite, DuckDB or Parquet research records.

## 10. Optional Supabase synchronization

Supabase is not a dependency for MIKA's first working release.

A later sync feature may use a dedicated project or carefully isolated MIKA schema for preferences, watchlists and selected summarized research records.

Requirements:

- Authenticated, user-owned records.
- Row Level Security for exposed tables.
- No service-role key in the desktop client.
- No access to DIT treasury or worker-auth tables.
- No replication of every high-frequency price observation.
- Conflict resolution between local and remote settings.
- Offline operation remains functional.

No Supabase migrations will be performed during the initial desktop build.

## 11. Local AI explanation layer

MIKA uses deterministic evidence compilation first, then optional Ollama enrichment.

The context supplied to an AI model consists of structured token identity, timestamped metrics, risk evidence, historical changes and relevant source references.

The AI may:

- Explain a suspicious indicator in plain language.
- Summarize what changed.
- Highlight counter-evidence.
- Explain why a claim remains unverified.
- Answer questions about the currently selected token.

The AI may not invent unavailable metrics, claim guaranteed safety, present an unverified wallet relationship as fact, or trigger trading actions.

If Ollama is unavailable, deterministic summaries continue working.

Untrusted token names, descriptions and social links are treated as data rather than instructions.

## 12. Character state machine

MIKA has a character state separate from the risk verdict.

| State | Trigger | Animation |
|---|---|---|
| `IDLE` | Connected, awaiting user attention | Blinking, subtle breathing and hair motion |
| `SCANNING` | An investigation is actively running | Focused eyes, glowing chip and small HUD animation |
| `WARNING` | A material risk finding appears | Serious expression, amber chip highlight |
| `ACTIVITY` | Meaningful market activity update | Curious smile, restrained violet/cyan particles |
| `THINKING` | Local model generating an explanation | Short focused expression and soft HUD pulse |
| `OFFLINE` | Core unavailable | Quiet idle portrait with disconnected label |

Character animations must reflect the real application state. They must not imply a successful analysis while data is still loading or has failed.

**State priority:** Offline overrides active animations. A high-severity warning overrides a cosmetic activity animation. The current investigation may continue behind a warning without hiding it.

## 13. Character assets

The existing MIKA character sheets are visual references, not yet production-ready transparent animation sequences.

Required assets:

- Full-body illustration.
- Half-body sidebar portrait.
- Square application icon.
- Small desktop-pet version.
- Idle loop.
- Scanning loop.
- Warning loop.
- Activity loop.
- Static fallback for reduced-motion mode.

For the first release, use consistent lightweight images and small UI transitions. True frame animation must use properly aligned, consistent character frames or a rigged model.

GIF export can be supported, but efficient animated WebP, APNG or equivalent native rendering is preferred for the runtime when suitable.

## 14. Desktop interface

Target default width: approximately 390 pixels.

Window behavior:

- Resizable Windows desktop panel.
- Optional always-on-top behavior.
- Right-side positioning.
- Minimize to system tray.
- Manual token search by mint address.
- Select a token from MIKA's research feed.
- Expand detailed evidence without covering the entire screen.
- Keep normal Chrome and GMGN browsing functional.

### Main navigation

**Scan:** Available new tokens and their evidence.

**Traction:** Previously observed tokens with meaningful changes.

**Watch:** Pinned tokens, history and notes.

**Ask MIKA:** Plain-language research questions tied to the selected token.

### Personalization

Allow the user to customize:

- Avatar mode: full body, half body, chibi or icon.
- Accent color.
- Eye and chip glow intensity.
- Animation intensity.
- Companion behavior: focused, playful or quiet.
- Notification sound and frequency.
- Desk-pet mode.
- UI density.
- Optional voice settings if speech capabilities are installed.
- Reduced-motion preference.
- Character nickname.

These options affect presentation, not risk-evidence standards.

## 15. Reliability and security

MIKA is research-only by construction.

The native API client may contact only configured trusted read-only endpoints. Access to JARVIS must be restricted to permitted GET routes rather than arbitrary local URL forwarding.

No wallet management, private keys, transfers, swaps, orders, automatic purchases or signing capabilities may be introduced.

Provider credentials remain outside the browser interface and source repository.

Failure states must be honest:

| Problem | Required behavior |
|---|---|
| JARVIS offline | Show disconnected state and cached history with timestamps |
| GMGN unavailable | Continue with supported non-GMGN research |
| Token absent from JARVIS universe | Fall back to available direct token research |
| Rate limit | Back off and label affected source unavailable |
| Conflicting providers | Preserve both claims and mark conflict |
| No holder data | Display unknown, not zero concentration |
| Ollama offline | Deterministic explanations remain available |
| Corrupted optional image | Display a default character asset |
| Missing animation frames | Use static fallback |
| Supabase disconnected | Continue locally |

## 16. First-release scope

The initial build must demonstrate a real, usable desktop companion rather than a static UI simulation.

**In scope:**

- Standalone MIKA window and icon.
- Working JARVIS connectivity.
- Read-only GMGN data integration.
- Visible real-token selection.
- Token evidence and source freshness.
- Clear risk classifications.
- Basic watchlist persistence.
- Limited historical change comparison.
- MIKA idle, scanning, warning and activity presentations.
- Customization basics.
- Honest disconnected and missing-data states.

**Deferred:**

- Comprehensive on-chain wallet ownership reconstruction.
- Reliable detection of coordinated bundle ownership.
- Machine-learning fraud claims without validated evidence.
- Browser DOM automation.
- 3D/Live2D production character rig.
- Cloud synchronization.
- Trading execution or wallet integration.

## 17. Acceptance criteria

The MVP is accepted only when:

- A real token can be selected and its contract identity is displayed correctly.
- Every displayed market value comes from a real observation or is shown as unavailable.
- Duplicate pools do not produce duplicate token identities.
- GMGN failures do not crash the application.
- A token outside JARVIS's canonical universe is handled explicitly.
- Risk findings link to their evidence class and source.
- Unknown security fields cannot silently produce a favorable verdict.
- At least one historical market change is calculated correctly from separate snapshots.
- Watchlist and settings persist after restarting MIKA.
- Character states correspond to actual application events.
- Offline mode retains readable cached information without pretending it is live.
- No trading, signing or wallet functionality is reachable through MIKA.
- The existing JARVIS and DIT installations remain unchanged.
- Relevant automated checks and Windows startup verification pass.

## 18. Delivery boundaries

**Milestone A — One-hour prototype target:** Desktop shell, core connectivity, basic token review, source display, and minimal personalization. This is contingent on the existing Windows/Rust environment and GMGN CLI working.

**Milestone B — Research completeness:** Stronger Solana verifier, durable structured history, detailed risk-evidence rules and robust traction comparisons.

**Milestone C — Character refinement:** Production-consistent animation assets, desk-pet interactions, richer customization and optional voice.

**Milestone D — Validation and optional sync:** Historical risk-rule evaluation, performance tuning, independent review and optional Supabase synchronization.

A feature is not considered completed until it has working behavior and corresponding verification—not merely an attractive mockup.

---

**Final design principle:** MIKA is a character-driven interface over verifiable research. Her personality makes the experience approachable; her intelligence comes from trustworthy observations, careful uncertainty handling and continuous historical context.
