# MIKA v0.2 verification ledger

- Local JavaScript tests: run `cd desktop && npm test` and record result below.
- JS syntax checks: `node --check` each `desktop/ui/*.mjs`.
- Rust compile, integration, and Windows installer: require CI/Windows; do not infer from JS tests.
- Live external feed behavior: requires network, configured providers and on-device smoke test. Mock tests validate parsing, not provider uptime.
- The previous v0.1 installer remains the known deployed version until a later v0.2 build is independently confirmed.
- New code must not permit buys, swaps, wallets, key handling or cloud LLM fallbacks.

## 0.4.1 source-level checks and limitations

- Node desktop tests: 83 passed on development container. Web: 3; cloud relay: 11; connector: 3; community policy: 3.
- Fixed Mayhem classification, provider-supplied social normalization, source fusion, strict social-only rows, filter view migration, source-separated first-sighting baselines and settings overlay.
- Windows WebView settings interaction, native Tauri build and live upstream Pump.fun/GMGN response require Windows GitHub CI plus manual owner smoke test; browser headless smoke-test was inconclusive in current environment.
- This change does not validate the underlying risk claims and does not deploy public services.
