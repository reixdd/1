# JARVIS Clean Rebuild — Step 3

> **0.3.1 fix:** this package resolves the Starlette conflict between the verified Step-2 FastAPI pin and OpenAI Agents SDK 0.22.3. It upgrades FastAPI to 0.142.2, pins Starlette 1.7.0, and validates the installed dependency graph with `pip check`.


Step 3 is the evidence/intelligence layer **on top of the already-proven Step 1/2 pipeline**.
It does not replace or fork SENSE, Market Tape, Universe, Quant, Experiments, River, or COLD science.

Canonical deterministic path remains:

```text
SENSE → BUS → TAPE → UNIVERSE → QUANT → EXPERIMENTS → RIVER → COLD
```

Optional Stage-3 side lanes consume canonical evidence asynchronously:

```text
canonical observations ─┬→ RISK
                        ├→ GRAPH
                        └→ SOCIAL/CALLER
                              ↓
                         STRUCTURED MEMORY
                              ↓
                       ATTENTION COMPILER
                              ↓
                 optional Agents SDK specialists
```

## Important boundaries

- No real orders, swaps, signing, transfers, or wallet mutation.
- No mystery `SAFE SCORE`; risk providers remain separate timestamped claims.
- Graph relationships are evidence, never automatic fraud labels.
- Project-published links are never counted as independent social corroboration.
- Agent conclusions are stored as `AGENT_CONCLUSION`, never silently upgraded into facts.
- Ollama and Agents SDK are optional intelligence. Disabling them must not stop the deterministic research pipeline.

## Runtime endpoints

- `/api/status`
- `/api/pipeline`
- `/api/research`
- `/api/evidence`
- `/api/evidence/risk?identity_key=...`
- `/api/evidence/graph?identity_key=...`
- `/api/evidence/social?identity_key=...`
- `/api/evidence/caller?source_id=...`
- `/api/memory/search?q=...`
- `/api/attention`
- `/api/agents`
- `/api/models`
- `/api/capabilities`

The three POST evidence endpoints are local research-ingestion boundaries for future read-only connectors. They do not execute external actions.
