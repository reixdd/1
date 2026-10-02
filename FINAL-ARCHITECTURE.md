# Final Architecture

```text
PUBLIC SENSE                    OPTIONAL READ-ONLY TOOLS
GeckoTerminal ─┐               GMGN official CLI ─────┐
DEX Screener ──┴→ EVENT BUS                               │
                     ↓                                    │
                 MARKET TAPE                              │
                     ↓                                    │
                  UNIVERSE                                │
                     ↓                                    │
                    QUANT                                 │
                     ↓                                    │
             PROSPECTIVE EXPERIMENTS                     │
                     ↓                                    │
                   RIVER                                  │
                     ↓                                    │
              DUCKDB / PARQUET                            │
                     ↓                                    │
        RISK / GRAPH / SOCIAL / MEMORY                    │
                     ↓                                    │
              SPECIALIST AGENTS                           │
                     ↓                                    │
                 ATTENTION                                │
                     │                                    │
                     └────────────┬───────────────────────┘
                                  ↓
                         OPERATOR COMPOSER
                                  ↓
                    CHROME JARVIS WORKBENCH
              ┌────────────┬──────────────┬─────────────┐
              │ MARKET     │ TOKEN        │ JARVIS      │
              │ RADAR      │ WORKSPACE    │ CHAT / MIC  │
              └────────────┴──────────────┴─────────────┘
```

## Ownership

The operator layer is a read/composition layer. It does not poll Gecko/DEX, create market observations, create experiments, label River samples, write COLD research results, schedule specialist agents, or own canonical token identity.

GMGN is also not made a second canonical scanner. It is queried through a bounded read-only bridge for human/operator enrichment. This avoids reintroducing the old multiple-owner failure mode.

## Browser boundary

`/workbench` and `/api/*` are served by the same local FastAPI process. Chrome therefore becomes a normal interaction layer, not a hidden scraper or a second runtime. The Core continues independently when Chrome closes.

## Legacy boundary

Old JARVIS files can inspire UX and can be inspected during migration, but no `backend.*` module is imported by the clean source tree. Legacy secrets are not generally copied; the final installer has one narrow exception for migrating the already-existing `GMGN_API_KEY` to the official CLI config when needed. No private/signing key is imported.
