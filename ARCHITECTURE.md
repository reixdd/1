# Step 3 architecture

## Frozen foundation

Step 1/2 ownership is frozen after live proof:

- SENSE: public market providers only
- EventBus: canonical observation ingress
- MarketTape: operational observations
- Universe: eligibility/current population
- Quant: deterministic/model-free features
- ExperimentEngine: prospective false→true transitions
- OnlineLearner: River predict→freeze→future-label→score→learn
- ColdArchive/Scientist: DuckDB/Parquet + chronological validation

Stage 3 may observe those systems; it may not become a competing owner.

## 3.1 Risk

`RiskBrain` stores provider claims as timestamped `SecurityEvidence` records. Multiple providers may disagree. Unknowns stay unknown. There is intentionally no synthetic safety score.

GoPlus is implemented as an optional bounded EVM adapter and is disabled until explicitly configured.

## 3.2 Graph

`GraphBrain` stores timestamped relations and analyzes them with NetworkX. It uses connected components and Louvain community detection on the evidence graph. Relationships remain evidence rather than fraud verdicts.

Current automatic graph evidence includes token↔pool, provider↔token, and security-provider entity fields when available. Future RPC/connectors can ingest wallet/funder/holder edges through the same canonical boundary.

## 3.3 Social / Caller

`SocialBrain` separates:

- PROJECT_PUBLISHED
- INDEPENDENT_MENTION
- CALLER_MENTION
- RECURRING_SOURCE

DEX profile links are project-published by definition. Caller outcomes are joined only to already-recorded prospective forward marks.

## 3.4 Memory

`MemoryBrain` preserves five classes:

- FACT
- OBSERVATION
- HYPOTHESIS
- UNVERIFIED_CLAIM
- AGENT_CONCLUSION

SQLite FTS is used for local retrieval when available. Search never changes an item's classification.

## 3.5 Agents / Attention

`OllamaCatalog` reads `/api/tags` at runtime and exposes the actual local model inventory. No model names are hard-coded into the UI/API.

One OpenAI Agents SDK runtime defines:

- SCOUT
- INVESTIGATOR
- SOCIAL
- CALLER
- QUANT_SKEPTIC
- REVIEWER
- SCIENTIST

JARVIS is the manager. Specialists receive bounded read-only tools. The manager uses specialists as tools, rather than creating another orchestration framework.

`AttentionCompiler` is deterministic and event-driven. It coalesces experiment/evidence changes into semantic packets:

- WHAT CHANGED
- WHY IT MATTERS FOR RESEARCH
- COUNTER-EVIDENCE
- HISTORICAL CONTEXT
- BASE RATE
- UNKNOWN

Agent enrichment is optional and cannot block packet creation or the core market/research path.
