# JARVIS Clean Rebuild — Step 3 report

## Implemented

- Risk evidence aggregation with explicit conflicts/unknowns and no synthetic safety score.
- Optional bounded GoPlus EVM token-security adapter.
- NetworkX entity graph with timestamped evidence, connected components and Louvain communities.
- Social/caller evidence that separates project-published from independent sources.
- Descriptive caller history joined to prospective 15-minute marks.
- Structured memory classes plus local FTS retrieval.
- Runtime Ollama model discovery; no fake/static model labels.
- One OpenAI Agents SDK manager/specialist hierarchy using local Ollama through its OpenAI-compatible endpoint.
- Bounded specialist tool sets.
- Deterministic semantic AttentionCompiler with counter-evidence/base-rate/unknown fields.
- Stage-3 evidence queue isolated from HOT/Quant/Experiments/River.
- Capability registry containing research/read-only capabilities only.

## Not claimed yet

- No Windows/Tauri shell (Step 4).
- No native notifications/tray/hotkey (Step 4).
- No legacy 14 GB database migration (Step 5).
- No automatic wallet/RPC graph ingestion yet; the clean graph boundary is ready for a future read-only connector.
- GoPlus is not enabled unless configured.
- Agent quality is not considered validated merely because the SDK/model runs. Agent conclusions remain a separate memory class.

## Local validation in the build environment

All dependency-independent tests pass. The OpenAI Agents SDK-specific surface test is skipped here because that package is not installed in the build container; the Windows installer installs pinned `openai-agents==0.22.3` and reruns the complete suite.

The deterministic Stage-3 smoke proves that evidence/attention can run with agents disabled while Quant still advances.

## 0.3.1 dependency compatibility fix

The original 0.3.0 lock combined `fastapi==0.128.2` (which constrains Starlette below 0.51) with `openai-agents==0.22.3` (which requires Starlette >=1.3.1), so pip correctly rejected the environment. 0.3.1 moves the core API framework to `fastapi==0.142.2` and pins `starlette==1.7.0`, a compatible pair with the Agents SDK requirement. The installer now runs `pip check` after dependency resolution and restores the Step 2 dependency lock if a later validation step fails.
