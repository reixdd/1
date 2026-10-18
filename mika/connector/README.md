# MIKA local AI connector (preview; not running by default)

This service opens **outbound HTTPS requests only** to the owner's configured Cloudflare Worker relay, then calls local Ollama (127.0.0.1:11434). Optional, fixed read-only JARVIS dossier lookup uses 127.0.0.1:8768. No visitor can request an arbitrary URL, model name, system role, filesystem path, wallet or command.

**Do not run this until the Cloudflare Worker has been deployed, assessed and device credential provisioned.**

Required environment variables (set privately on the Windows device; never commit):

- `MIKA_PUBLIC_ENABLED=1` — deliberate owner opt-in. Default off.
- `MIKA_PUBLIC_RELAY_ORIGIN=https://YOUR-OWNED-MIKA-DOMAIN` — exact HTTPS origin for the relay.
- `MIKA_PUBLIC_CONNECTOR_TOKEN` — long randomly-generated credential, matching Worker secret `LOCAL_CONNECTOR_SECRET`.
- `MIKA_PUBLIC_CHAT_MODEL=qwen3.5:4b` — optional installed local text model. No embedding models.

Keep Ollama on localhost; **never forward or expose port 11434**. Launch from `connector/` with `node connector.mjs`. Stop with Ctrl+C to turn serving off; visitor status goes offline after 30 seconds.

No cloud LLM fallback. The initial version uses a simple polled, at-most-one-running-job queue and a 110-second inference budget. No automatic background install or startup task.
