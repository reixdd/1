# Step 3 live acceptance

After installation and verification, start clean JARVIS and check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8768/api/pipeline" | ConvertTo-Json -Depth 20
Invoke-RestMethod "http://127.0.0.1:8768/api/evidence" | ConvertTo-Json -Depth 20
Invoke-RestMethod "http://127.0.0.1:8768/api/models" | ConvertTo-Json -Depth 20
Invoke-RestMethod "http://127.0.0.1:8768/api/agents" | ConvertTo-Json -Depth 20
Invoke-RestMethod "http://127.0.0.1:8768/api/attention" | ConvertTo-Json -Depth 20
```

Core gate: the proven Step-2 counters continue moving.

Stage-3 gate:

- graph edges/nodes accumulate from canonical observations;
- DEX profile links appear only as `PROJECT_PUBLISHED` social evidence;
- capability registry contains read-only capabilities only;
- `/api/models` displays actual locally installed Ollama model names when Ollama is running;
- attention packets appear on prospective experiment/evidence transitions rather than on every provider call;
- no `safe_score` is synthesized.

## Required failure-isolation test

With JARVIS running, record `/api/pipeline`. Stop Ollama, wait for more public-market observations, then query `/api/pipeline` again.

These must continue increasing with Ollama offline:

- provider_observations
- event_bus_in/out
- tape_accepts
- universe_applies
- quant_evaluations
- experiments/forward_marks/online labels as their prospective conditions mature

`/api/agents` may report Ollama unavailable. That is expected. Core research must not stop.
