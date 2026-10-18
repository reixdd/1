# MIKA — Market Intelligence & Knowledge Assistant

MIKA is a research-only Windows desktop sidebar, built with Tauri 2 and designed to read the **existing JARVIS research core**. It is not a trading bot, not a wallet tool, and not a guarantee that any memecoin is safe. It does not write to JARVIS's database or require Supabase.

## Status — October 18, 2026

- **Implemented in source:** native 400px Tauri sidebar configuration, local read-only API allowlist, Solana token identity normalization, JARVIS radar UI, GMGN token fallback, evidence-attributed risk classifications, traction comparison, local watch preferences, deterministic Ask MIKA, generated character portraits and states.
- **Verified in this build environment:** Node unit tests (`npm test`), JavaScript syntax checks, source archive contents.
- **Not verified here:** Windows Tauri compile/install, genuine live GMGN credentials/connectivity, browser-based UI screenshot test, native tray behavior. Rust/Cargo is not installed in this execution environment.
- **Not included:** real-money trading, reliable common-owner/bundle attribution, direct Solana RPC verifier, full GIF/Live2D animation, Cloud sync, natural-language Ollama chat (Ask tab uses transparent deterministic replies).

## Windows setup

1. Install Rust (stable, >=1.90), Microsoft Visual Studio C++ Build Tools and Microsoft WebView2 runtime, plus Node.js 20+.
2. Start the existing JARVIS backend at `http://127.0.0.1:8768`. Validate `http://127.0.0.1:8768/health` in a browser; its `ok` value must be true.
3. From the `mika/desktop` folder run:

```powershell
npm.cmd install
npm.cmd test
npm.cmd run dev
```

4. Test a real Solana mint address in MIKA's Scan view. GMGN data requires a correctly configured GMGN CLI on the JARVIS side. If GMGN is unavailable, it will say so; JARVIS radar may still work via its alternative discovery providers.
5. Once native checks succeed, package a Windows installer with `npm.cmd run build` from `mika/desktop`. Do not claim a distributable installer exists until it passes on Windows.

For a code-only browser preview, serve `desktop/ui/` using a local static server. It displays **CORE OFFLINE**, not fake market data, because native bridge calls are only available in Tauri.

## Security boundaries

The Rust bridge only permits specific GET routes on `127.0.0.1:8768`; it rejects unknown paths, unsupported query parameters, request injection, redirects and large responses. The window never fetches external token images or executes token descriptions as HTML. Neither private keys nor wallet actions are supported. MIKA uses provider-reported data as **claims**, never as independent confirmation. `UNKNOWN` is not zero and is not proof of safety.

## Directory structure

```
desktop/
  src-tauri/      native window, bridge, icon, installer config
  ui/             standalone accessible frontend + MIKA portraits
  tests/          Node built-in unit tests
  package.json    dev/test/build commands
docs/             Superpowers design and plan (in staging branch)
```

## GitHub isolation

Current working branch: `reixdd/1` → `mika-isolated-project`, under directory `mika/`. **Do not merge it into JARVIS main.** The connected GitHub integration cannot create repositories. Once a dedicated `reixdd/mika` repository exists, move this directory to that repository root. Until then, a tested code archive can be downloaded directly from this conversation.
