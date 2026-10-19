# v0.3 verification record (October 18, 2026)

## Verified locally with Node.js 22

Run from each directory: `npm test` in desktop, web, cloud, connector; `node --check` on every ES module.

- Desktop tests: token provenance, media/social validation, comparable cap bars, risk/unknown fields, AI model filters, watch persistence and snapshot changes.
- Web transport tests: same-origin routing, malformed mint rejection, explicit provider error states.
- Cloud tests: signed sessions, challenge enforcement, exact Origin, device bearer token, queue capacity and rate caps, job ownership, lease replay and expiration, full mocked job lifecycle.
- Connector tests: default public OFF, HTTPS relay URL, embedding-model rejection and sanitized market context.

## Not verified here

- Cloudflare Worker/Durable Object production runtime and quotas; no public deployment.
- Cloudflare Turnstile real issuance and browser UI rendering.
- Windows Rust build after v0.3 changes (local container lacks cargo); GitHub Actions build needed.
- Live provider feeds; upstream API caching and rate limiting vary.
- Real Ollama model inference on owner's PC; v0.3 timeout/config was checked in source only.
- Browser preview blocked by sandbox browser policy; static asset server served index with HTTP 200, but browser rendering smoke test was unavailable.
- Complete security review by independent reviewer, production penetration tests, human moderation/abuse testing.

The earlier v0.2 installer remains your known last installed version until v0.3 Windows CI and the on-device smoke test pass.


## v0.4 development verification
Desktop 71, web 3, cloud 11, connector 3, community 3 JS tests passed locally. Windows build, GMGN real-API smoke test, on-chain creator history and production feedback backend are pending independent verification. No public reports endpoint deployed.
