# JARVIS Clean Rebuild — Step 2 Report

## Scope

Step 2 extends the already-clean Step 1 nervous system without adding a second market loop.
The canonical path remains:

`SENSE -> EventBus -> MarketTape -> Universe -> Quant`

Step 2 adds only:

`Quant -> Prospective Experiments -> River Online Validation -> DuckDB/Parquet Cold History -> Scientist`

No legacy `backend`, V12/V13, watcher, scanner, browser/CDP, trading execution, or old database is imported.

## Experiment engine

- Opens research experiments only on persisted false -> true transitions.
- Current neutral cohorts are `ACTIVE_MARKET_TRANSITION`, `MULTISOURCE_TRANSITION`, and a deterministic 5% `RANDOM_CONTROL` sample.
- Scientific sampling is not gated by a pretend bankroll.
- Entry market/Quant state is frozen at T0.
- Forward horizons: 5m, 15m, 30m, 1h, 3h, 6h, 24h.
- Forward tracking pins experiment identities for reconciliation after they age out of the young HOT universe.
- Marks include completeness plus prospective return/MFE/MAE descriptors; these are research outcomes, not order instructions.

## Online learning

- River is the only online-learning implementation.
- Protocol is strict: `predict -> freeze -> wait -> future label -> score -> learn`.
- Step 2's first model target is deliberately neutral: whether 15-minute liquidity remains at least 75% of T0 liquidity.
- ADWIN monitors prediction-error drift.
- Predictions persist their frozen T0 feature lineage.
- Restart reconstruction replays only already-matured predictions in chronological order.
- River failure/missing dependency does not stop HOT or experiments; status reports the dependency failure explicitly.

## Leakage gate

The shared `LeakageAuditor` rejects:

- features frozen after prediction time,
- labels observed before their due time,
- feature names containing future/label/MFE/MAE/forward-return information.

A failed leakage audit blocks online learning for that record.

## Cold research history

- SQLite/WAL remains bounded operational state.
- A durable SQLite outbox decouples live research from cold writes.
- DuckDB is the queryable historical research store.
- Parquet is exported in coarse sequence batches using ZSTD and 122,880-row groups instead of one tiny file per observation.
- On shutdown, pending cold rows are flushed and a final Parquet export is forced.

## Scientist

- Reads archived prospective predictions only.
- Chronological train/validation/test split.
- Purge window between chronological partitions.
- Untouched test is used only for final reporting.
- Deterministic bootstrap interval for validation base rate.
- Optuna may propose a validation threshold; result is explicitly `PROPOSAL_ONLY` and is never deployed automatically.
- Scientist cannot rewrite live hypotheses.

## Failure isolation

- Missing River: SENSE/Tape/Universe/Quant/Experiments continue.
- Missing DuckDB/Polars: live path continues and cold/science status reports unavailable.
- Scientist exceptions are independently supervised.
- Cold archive exceptions are independently supervised.

## Tests in this build environment

The build container cannot download River/DuckDB/Polars/PyArrow, so actual-library tests are conditionally skipped here. All dependency-independent tests pass. The Windows installer installs pinned research packages first, then runs the complete test suite and `python -m jarvis.stage2_smoke`, which exercises the real installed River/DuckDB/Parquet stack.

## Not Step 2

Deliberately absent until later gates:

- Agents SDK specialist team
- Ollama integration
- Social/Caller/Graph/Risk
- Attention compiler redesign
- Tauri/Windows shell
- old 14 GB database migration
- legacy workstation frontend
- real order/swap/sign/transfer execution

## Windows install correction (0.2.1)

The first Windows Step-2 attempt exposed two DuckDB lifecycle defects that did not reproduce in the dependency-limited build container:

1. COLD readers used `read_only=True` while archive/status writers used read/write connections to the same DuckDB file, which DuckDB rejects as different configurations within the same database instance.
2. Isolated API/pipeline tests could request archive status before `ColdArchive.open()` had created `research_events`.

The corrected Step 2 keeps one read/write access mode for the single JARVIS process, serializes short-lived DuckDB I/O behind the COLD archive gate, and lazily ensures the COLD schema before status/query operations. A regression test covers status-before-open plus concurrent status/query access.
