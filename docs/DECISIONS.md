# Decisions

- 2026-11-15: Build Hatch's own runtime; do not call `api.inya.ai` or claim Gnani Agent Builder deployment.
- 2026-11-15: Keep all Gnani traffic serial through a concurrency-one gateway until account limits are confirmed by Gnani.
- 2026-11-15: Use REST push-to-talk for browser audio first; realtime WebSocket is deferred because it needs a paced backend proxy and its account limits are unknown.
- 2026-11-15: A serial authenticated probe confirmed `prisma-v2.5`, `prisma-v3.0`, `timbre-v2.5`, and `timbre-v3.0` access, plus the configured OpenAI-compatible LLM. Prefer Prisma v3.0 with `indic-auto`/`codemix` and Timbre v3.0 for supported requests; probe sample results are in `VERIFIED_GNANI.md`.
- 2026-11-15: Do not run concurrency, rate-limit, or invalid-key tests against the provider. Keep concurrency one until Gnani confirms account limits.
- 2026-11-15: Leave cost estimates uncalibrated until the owner records before/after dashboard balances. Enforce the configured hard spend ceiling and degrade to text when cost is unknown.
