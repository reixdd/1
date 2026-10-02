# JARVIS Final Operator Workbench

This package finishes the clean rebuild by putting a practical crypto research workstation around the already-proven JARVIS Core 0.3.1.

## Product model

- **JARVIS Core** stays in the background and continues the proven provider → bus → tape → universe → Quant → prospective experiment → River → COLD/evidence/attention pipeline.
- **Chrome Workbench** is now the primary operator surface at `http://localhost:8768/workbench`.
- **Legacy aitrader** is a reference/parts bin only. The final installer does not import any legacy Python backend, scanner, database owner, launcher, or frontend runtime.
- **GMGN** is restored as an optional read-only enrichment source through the official `gmgn-cli`. Only `market` and `token` query commands are allow-listed. No swap/order/cooking/private-key capability exists in this build.

## Practical workstation

The workbench provides:

- live canonical token radar with LIVE / SURGING / WATCHED queues;
- separate optional GMGN HOT and GMGN NEW tabs;
- symbol/contract search and GMGN fallback lookup;
- selected-token dossier with market cap, liquidity, volume, buys/sells, age, rank and rank velocity;
- local live market-tape chart;
- JARVIS brief: WHAT CHANGED / SUPPORT / COUNTER-EVIDENCE / UNKNOWN;
- Security, Relationships, Social, Research and GMGN evidence tabs;
- persistent watchlist;
- X and DEX Screener browser-research shortcuts;
- real JARVIS chat tied to selected-token context;
- FAST and DEEP modes over the existing bounded local-agent team;
- microphone input via the browser Web Speech API when supported;
- optional local browser speech output;
- Chrome notifications for new semantic attention packets;
- activity log and hidden engineering/system-health drawer;
- small workstation personality details, sounds and cat status line without turning the UI into gamer RGB.

The workbench intentionally does **not** expose buy/sell/swap/signing/transfer controls. It is a research console.

## Install

From the extracted package folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Install-JARVIS-Final-Workbench.ps1 -InstallRoot "$env:USERPROFILE\JARVIS"
```

The installer:

1. verifies clean Core `0.3.1` and `pip check`;
2. safely stops only a process positively identified as clean `python -m jarvis` on port 8768;
3. backs up the current source/scripts;
4. copies only the final operator/source layer — **no pip dependency changes, npm, Rust or Cargo**;
5. runs compile, dependency, unit and research-only audits;
6. migrates only `GMGN_API_KEY` from legacy `data\v4-secrets.env` to the official GMGN global config if the global key is missing;
7. never migrates a GMGN private/signing key;
8. optionally verifies `gmgn-cli config --check` if the official CLI is installed;
9. creates a Desktop `JARVIS Workbench` shortcut;
10. restarts the clean Core if it was already running.

## Start

Double-click the Desktop shortcut, or run:

```cmd
%USERPROFILE%\JARVIS\JARVIS-WORKBENCH.cmd
```

This starts the clean Core in the background if needed and opens normal Chrome to:

```text
http://localhost:8768/workbench
```

Closing Chrome does not stop the Core.

## Verify

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Verify-JARVIS-Final-Workbench.ps1 -InstallRoot "$env:USERPROFILE\JARVIS"
```

For a compact live diagnostic:

```powershell
& "$env:USERPROFILE\JARVIS\Get-JARVIS-Diagnostics.ps1"
```

## GMGN

Current official GMGN Skills documentation recommends the global config file:

```text
~/.config/gmgn/.env
```

with `GMGN_API_KEY`. This package checks that location. If it is empty but the old JARVIS `data\v4-secrets.env` contains an API key, the installer copies **only** `GMGN_API_KEY` into the global config without printing the value.

The runtime wrapper only permits these read-only families:

- `gmgn-cli market trending`
- `gmgn-cli market trenches`
- `gmgn-cli market search`
- `gmgn-cli market kline`
- `gmgn-cli token info`
- `gmgn-cli token security`
- `gmgn-cli token pool`
- `gmgn-cli token holders`
- `gmgn-cli token traders`

The wrapper uses argument lists rather than shell interpolation, validates chain/address inputs, caches queries, serializes calls, and cools down after rate-limit errors.

GMGN's own documentation says token metadata is external/untrusted content. JARVIS therefore displays it as evidence and never interprets metadata text as instructions.

## Chrome layer

Chrome is deliberately the main interactive surface. JARVIS serves the workbench from the same localhost origin as its API, so there is no external SaaS frontend or browser automation dependency. The browser is free to remain a normal Chrome window with X, Discord, research sites and other tabs beside JARVIS.

Microphone input uses `SpeechRecognition` / `webkitSpeechRecognition` when the browser exposes it. It degrades honestly if unsupported. Chrome implementations may use a server-based recognition engine, so microphone availability is not assumed to be offline.

## Legacy retirement

Do **not** delete the old project immediately. First run:

```powershell
& "$env:USERPROFILE\JARVIS\Audit-Legacy-JARVIS.ps1"
```

After you have used the final workbench and confirmed it contains the practical tools you need, retirement can be performed with the package's `Retire-Legacy-JARVIS.ps1 -Confirm`. It only renames the legacy directory to an `OFFLINE-LEGACY-*` path; it does not delete history.

## External research used for this build

- GMGN official skills/CLI repository and current `gmgn-market` / `gmgn-token` skill documentation.
- OpenAI Agents SDK current manager-as-tools and runner/streaming documentation.
- Chrome localhost / Local Network Access guidance.
- MDN Web Speech API documentation for optional microphone behavior.

See `RESEARCH-NOTES.md` for exact design decisions.
