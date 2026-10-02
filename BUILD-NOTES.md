# Step 3 build notes

Research decisions used for this implementation:

1. OpenAI Agents SDK is used directly for manager/specialist orchestration. JARVIS does not implement a second custom agent loop.
2. Local Ollama is connected through its OpenAI-compatible chat-completions interface. Installed model names are discovered through `/api/tags` at runtime.
3. NetworkX supplies connected-components and Louvain community analysis instead of bespoke graph-clustering heuristics.
4. GoPlus is treated as one security-evidence provider. Its fields remain provider claims and are never collapsed into a mystery score.
5. Stage-3 observations travel through a bounded side queue so graph/social/risk failures cannot add latency to HOT/Quant/Experiment/River.
6. Agent prompts explicitly prohibit action recommendations and transaction behavior. Stage 3 is research interpretation only.

The clean rebuild still has no runtime import from `backend`, `aitrader`, V12, V13, or any legacy scanner/watcher tree.
