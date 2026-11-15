# Decisions

- 2026-11-15: Build Hatch's own runtime; do not call `api.inya.ai` or claim Gnani Agent Builder deployment.
- 2026-11-15: Keep all Gnani traffic serial through a concurrency-one gateway until account limits are confirmed by Gnani.
- 2026-11-15: Use REST push-to-talk for browser audio first; realtime WebSocket is deferred because it needs a paced backend proxy and its account limits are unknown.
- 2026-11-15: A serial authenticated probe confirmed `prisma-v2.5`, `prisma-v3.0`, `timbre-v2.5`, and `timbre-v3.0` access, plus the configured OpenAI-compatible LLM. Prefer Prisma v3.0 with `indic-auto`/`codemix` and Timbre v3.0 for supported requests; probe sample results are in `VERIFIED_GNANI.md`.
- 2026-11-15: Real Timbre v3.0 rejected `speed="medium"` with HTTP 400 although docs list symbolic values; omit it or send numeric `1.0`. Hatch uses numeric speed.
- 2026-11-15: Do not run concurrency, rate-limit, or invalid-key tests against the provider. Keep concurrency one until Gnani confirms account limits.
- 2026-11-15: Dashboard unit prices were unavailable, so use conservative planning estimates (`STT_COST_INR_PER_SECOND=0.05`, `TTS_COST_INR_PER_1000_CHARS=0.50`) and stop at 70% of `CREDIT_BUDGET_INR`. This unblocks the live demo while overstating spend; override with measured rates in `.env`. See `CREDITS.md`.
- 2026-11-15: The configured OpenAI-compatible provider rejects JSON mode unless a message contains lowercase `json`; the structured-output gateway now states that requirement explicitly.
- 2026-11-15: Allow any loopback Vite origin (`127.0.0.1` or `localhost`, any port) through CORS so a port shift does not break the demo; do not allow remote origins.
- 2026-11-15: Split spoken replies into chunks of at most 180 characters, synthesize each through Timbre, and play them sequentially in the browser. This avoids long single-request TTS failures and starts audio sooner.
- 2026-11-15: Every speech failure surfaces in the UI with a text-input fallback; no error is silent.
