# Research notes for the final operator rebuild

## GMGN

The current official `GMGNAI/gmgn-skills` documentation treats `gmgn-cli` as the structured-data interface and recommends `~/.config/gmgn/.env` with `GMGN_API_KEY`. Current market skills expose trending, trenches, signal, hot searches, search and kline. Current token skills expose info, security, pool, holders and traders. Rate limits are plan-based and weighted, so the final bridge caches and serializes calls instead of turning GMGN into another high-frequency scanner.

The GMGN docs explicitly warn that token metadata and external content are attacker-controlled text. The bridge therefore validates chain/address values before executing a process, uses `subprocess.run([...])` without a shell, and treats all returned text as data.

The official project also contains swap/order/cooking capabilities. Those are intentionally absent from the final bridge. `GMGN_PRIVATE_KEY` is neither read nor migrated.

## Agents

The current OpenAI Agents SDK supports manager-style orchestration where specialist agents are exposed as tools to a manager. The existing clean JARVIS Stage 3 already implemented that shape. The final workbench adds a conversational `ask()` entry point to the same bounded team instead of creating a second chatbot/agent runtime.

The operator chat injects selected-token and radar context, but the specialists still read canonical state using bounded tools. Market polling remains outside the LLM path.

## Chrome

Chrome's current Local Network Access work continues to tighten cross-site requests into loopback/local networks. Serving both the UI and API directly from the local JARVIS origin avoids the design where a public/remote frontend reaches into localhost.

The final launcher opens normal Chrome rather than embedding a browser automation stack. This keeps Chrome usable as a separate research layer with normal tabs and sessions.

## Voice

The browser workbench uses Web Speech API recognition only when exposed by the browser. MDN still classifies `SpeechRecognition` as limited availability and notes that Chrome can use a server-side recognition engine, so the feature has an explicit unsupported/error state rather than pretending voice is always local or available.

## Legacy UX comparison

The old build's most useful ideas were not its backend ownership model; they were its practical operator surfaces: live candidates, selected-token dossier, persistent command/chat input, visible activity, source links, watch/research flow, and workstation personality. The final workbench selectively recreates those interaction patterns over the clean Core while leaving old scanners, database ownership, provider loops and launchers offline.
