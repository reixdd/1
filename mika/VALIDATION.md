# MIKA v0.2 verification ledger

- Local JavaScript tests: run `cd desktop && npm test` and record result below.
- JS syntax checks: `node --check` each `desktop/ui/*.mjs`.
- Rust compile, integration, and Windows installer: require CI/Windows; do not infer from JS tests.
- Live external feed behavior: requires network, configured providers and on-device smoke test. Mock tests validate parsing, not provider uptime.
- The previous v0.1 installer remains the known deployed version until a later v0.2 build is independently confirmed.
- New code must not permit buys, swaps, wallets, key handling or cloud LLM fallbacks.
