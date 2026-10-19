# MIKA v0.4 — Evidence Radar and Three-Tab Interface (Design)

**Date:** 2026-10-18
**Status:** Design draft for user review; product implementation not authorized by this document.
**Base:** `reixdd/1` branch `mika-v032-media-traction-repair`; staging branch `mika-v04-evidence-and-creator-memory-design`.
**Goal:** Keep MIKA research-only while making Pump.fun observations actionable as *evidence*, with honest GMGN metrics, configurable research filters, deep links and compact summaries.

## Product intent and scope

User wants MIKA to surface new Pump.fun tokens, display which token-risk checks are supported, filter the noisy Traction view, link to the exact token in GMGN and X, and stop offering the unreliable Ask UI. MIKA must not rank guaranteed-safe assets, prompt trades, sign transactions or treat an AI narrative as security evidence.

Two independent specs under this release:
1. **This spec:** read-only feed/metrics/desktop UX and research filtering.
2. **`2026-10-18-mika-v04-creator-evidence-and-community-design.md`:** verified creator history, moderated feedback and optional public persistence. These must not block shipping the desktop evidence fixes.

## Alternatives and recommendation

- **Chosen:** Enrich existing `normalizeTrenches` feed, then request `/api/operator/gmgn/token` only for selected/watchlisted or prioritized visible mints. Keep the read-only JARVIS bridge and a bounded queue. Reliable source attribution, modest request load, no changes to JARVIS main.
- **Not chosen:** GMGN web DOM scraping or treating website HTML as a market API. It breaks easily and has different policy/availability constraints.
- **Not chosen:** Make every visible token call `holders=true` each second. Excessive rate limit load and misleading freshness. Token security caching is independent of market quotes.

## Current repo findings

The v0.3.2 `domain.mjs` *already* preserves `bundler_rate` and `holder_concentration_rate`; prior dropped-fields explanation applies to older versions, not current branch. However, the card only shows ratios exceeding the earlier warning thresholds, and otherwise says checks unavailable—even when GMGN explicitly reports a valid zero or low ratio. `token()` may fall back to GMGN without canonical history, and token info/security is a different response shape from Trenches. `risk.mjs` unwraps the security bundle for full dossier but cards do not use that evidence. Default Trenches currently only requests `new_creation`. X is missing if source returns a top-level `twitter` URL/handle outside the metadata normalization path. Ask still appears in `index.html` and is wired in `app.mjs`.

GMGN official skill docs use 0–1 ratios for bundler/top-holder fields, and publish `--max-bundler-rate` and `--max-marketcap` server-side filters. An absent ratio may be excluded by server-side filtering. We should retain unfiltered discovery locally and classify unknowns, so unknown tokens remain visible in an Unverified tab. Reference: `https://github.com/GMGNAI/gmgn-skills/blob/main/skills/gmgn-market/SKILL.md`.

Verified token-page pattern: `https://gmgn.ai/sol/token/{base58_mint}`. Only construct this for a valid Solana mint. Tokens may lack a source-provided X account; never infer one.

## Data model

Normalized `TokenResearchRecord`:
- `chain:'sol'`, `mint:string`, `market_key:string`, `symbol:string`, `name:string`.
- `market`: `market_cap_usd|null`, `liquidity_usd|null`, `volume_5m_usd|null`, `buys_5m|null`, `sells_5m|null`, `price_change_5m_pct|null`, `source`, `observed_at`.
- `profile`: `image_url|null`, `x_url|null`, `gmgn_url`, `source_url|null`.
- `gmgn`: `bundler_ratio|null`, `top10_holder_ratio|null`, `dev_team_hold_ratio|null`, `insider_ratio|null`, `rug_ratio|null`, `mint_renounced:boolean|null`, `freeze_renounced:boolean|null`, `creator_address:string|null`, `source_kind:'TRENCHES'|'TOKEN_SECURITY'|'UNKNOWN'`, `observed_at|null`.
- `evidence`: typed findings with `provider`, `raw_field`, `raw_value`, `normalized_value|null`, `classification`, `timestamp`, and `unknown_reason`.

Values from Trenches and token security must never be silently merged without preserving which snapshot supplied each field. Null is unknown; explicit 0 is a measured value. No inference from percent display text. Supported ratios bounded `0<=r<=1`; if an upstream source yields out-of-range values, retain raw field and label unknown, never divide by 100 heuristically.

## Pump.fun research feed and enrichment

- Existing GMGN/GeckoTerminal read-only discovery stays. Deduplicate by case-sensitive Solana mint, preserve separate pools.
- Hydrate only visible/selected/watchlist candidates via existing JARVIS GET route `/api/operator/gmgn/token?chain=sol&address={mint}&holders=false` initially; holders can be requested when the detail panel is opened. Use global concurrency 2, minimum 60s security cooldown per mint and exponential backoff for rate limits.
- Cache successful security observations for 60 seconds (or provider timestamp policy) and do not change its `observed_at` on re-render. Market quote polling cadence does not refresh security evidence.
- Show known 0% and known below-threshold values explicitly rather than "checks unavailable". Unknown appears independently and is never classified as passing.
- When direct token lookup fails, retain the launch row with its provider attribution and `UNVERIFIED` checks.
- For social links, normalize `socials[]`, `twitter`, `twitter_url`, `twitter_username` only when a valid explicit handle/URL is provided by the provider; validate exact x.com/twitter.com host and refuse other arbitrary pages.
- For artwork, retain existing DIT-compatible validated HTTPS source handling and fallback avatar, with a badge if no usable image is provided.

## Default adjustable Traction filters

Filters are for **research organization, not approval to buy**:
- Market cap **under $30,000**, adjustable 0–$250,000 with toggle off.
- GMGN provider-reported bundler ratio **under 30%**, adjustable 0–100% with toggle off.
- State chips `Within selected filters`, `Outside filters`, `Unverified`. A token with unknown bundler ratio MUST NOT appear as a confirmed pass. Default view is `Within selected filters` plus visible `Unverified` count.
- Additional optional sort: newly observed, 5m activity, 5m buy/sell imbalance, market cap. A high buy count or price increase is never labeled a winning token.
- A one-screen summary per card, e.g. market-cap value + 5m volume/buy/sell + `GMGN bundler: 8% (reported 20:15)` + `Top 10: unknown` + one factual risk/unknown note.
- Bars remain 5m **transaction-count balance** or **relative market-cap scale**, with plain labels/legend and data timestamp. Neither bar implies net buying USD or wallet ownership.
- Prior unseen token can display immediate provider 5m metrics; historical comparisons only after compatible timestamped observations. Never manufacture baseline changes.

## UI layout: three tabs

- Navigation `Scan | Traction | Watch`, remove Ask tab and visible Ask form, model selector and chat scroll. Keep local Ollama capability out of this release's desktop UI; no need to delete the backend model commands immediately because website architecture may reuse them.
- Scan: rolling Pump.fun token list and inspection panel with full CA/copy, image, 5m buys/sells, liquidity, security evidence, GMGN deep link and X icon only if verified social metadata available.
- Traction: cards ordered/filtered by explicit preferences, with both volume and risk evidence, GMGN deep link, source-specific timestamp and creator-history slot (unknown until phase 2).
- Watch: full CA and one-tap copy, market cap/volume/buy-sell, X and GMGN, creator-history slot, last-seen time. Prefer no social icon over fabricated link.
- Persist filters/selection in `createPreferencesStore` under a migrated versioned preferences shape; existing watchlist is preserved. Reduce chat state re-renders.
- Use accessible button titles, visual focus, one tap links (`target="_blank"`, `rel="noopener noreferrer"`).

## Security & responsible classification

Four visibility states: `WARNING`, `REVIEW`, `NO_MAJOR_FLAGS_REPORTED`, `UNVERIFIED`. Low provider bundling is **not** safety, and all numerical risk rules expose the exact supported field/threshold/source. Do not publicly accuse any creator of fraud based solely on indicators.

This first phase is **read-only** and does not change JARVIS, creator history or community feedback. No trades, auto buys, wallets, hot keys for trading, or manipulation detection claims beyond evidence.

## Test and release gates

1. GMGN valid `bundler_trader_amount_rate:0` displays 0%, not unavailable; high ratio displayed with provider/time.
2. Missing or out-of-range bundled/holder values stay unknown; no favorable classification.
3. Combined rows retain per-field source/provenance; no stale "live" security label.
4. Exact valid mint constructs an openable `gmgn.ai/sol/token/{mint}` link; invalid mint does not.
5. Source-provided Twitter URL from top-level field is accepted; unsafe or inferred URLs rejected.
6. Default $30k and 30% filters isolate verified fits while preserving separate unverified count and user-adjustable values.
7. Existing watchlist, quote updates and image handling survive migration.
8. Tabs are exactly Scan/Traction/Watch; page has no Ask view, chat form or model dropdown.
9. Render has evidence-referenced, compact summary not unsupported hype.
10. Full Node tests and GitHub Windows installer build complete before new download link. Live provider smoke test on owner's Windows PC is separately required; report unverified until done.

## Delivery order

First implement data normalization + source attribution, then GMGN detail hydration and display, then filters/summary, then three-tab UI and regression suite. Package as `0.4.0-rc1` on isolated branch only, never merge into JARVIS main. Creator memory/feedback can ship independently after its own design gate.

## Personalization addendum (approved 2026-10-18, lower priority)

Preserve existing lavender/mint/ice presets and add charcoal-white, rose, and amber accents plus an optional custom hex accent (#RRGGBB only, no arbitrary CSS). Keep portrait/full-body/icon, reduced-motion, compact/dense display choices, and on-device persistence after the evidence and Traction fixes are verified. Color selection is presentation-only, must not override semantic warning/status colors or evidence provenance, and must not change the backend or incur image-generation/LLM work. Tests must cover invalid custom colors and preference migration without losing watchlist or saved research.

