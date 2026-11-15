# AGENTS.md — Hatch

Hatch is a voice-agent compiler. A user describes a voice agent out loud; Hatch transcribes it (Gnani Prisma STT), compiles a provenance-tracked AgentSpec, tests it with simulated callers, repairs it, and serves it at `/a/<id>` where the user can talk to it (Gnani Timbre TTS). Tagline: *Say it. Hatch it. Talk to it.*

## Source of truth (read in this order before any code)
1. `docs/03_COPILOT_MASTER_PROMPT.md` — your instructions, rules, phases, schemas.
2. `docs/01_GNANI_PLATFORM_FACTS.md` — verified Gnani API facts and unknowns.
3. `docs/02_PRODUCT_AND_ARCHITECTURE.md` — architecture and scope tiers (P0/P1/P2).
4. `docs/04_EVAL_DEMO_RISKS.md` — evaluation, demo script, review bundle format.
If a doc conflicts with what the real API does, the real API wins. Record it in `docs/DECISIONS.md` and `docs/VERIFIED_GNANI.md`.

## Environment
- Windows 11, PowerShell, repo root `C:\Users\Srishti Pandey\hatch`. No `make`, no bash. Use Python scripts and npm scripts. Use `pathlib`.
- Python 3.11+, Node LTS, ffmpeg on PATH. Install missing tools yourself (`winget install Gyan.FFmpeg`).
- Backend: FastAPI, httpx, pydantic v2, SQLite. Frontend: React, Vite, TypeScript.
- Secrets live in `.env` (GNANI_API_KEY, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL). Never print, log, commit or echo them. Keep `.env.example` with placeholders only.

## Autonomy
- Work continuously. When something fails, diagnose and fix it yourself, then move on. Do not stop to report individual failures.
- Stop only for: a missing credential, a decision that cannot be undone, or a scope question the docs do not answer. Otherwise decide, and write the decision in `docs/DECISIONS.md`.
- Never claim something works unless you ran it and saw it work. Mark each feature `DONE (verified by: <command>)`, `PARTIAL`, or `NOT DONE` in `review/phase_N/STATUS.md`.

## Deadline and cut order
Submission closes 15 Nov 2026 18:00 IST. A working end-to-end demo must exist by 15:00 IST. Cut P2 first, then P1. P0 is: mic capture, transcript, compiled spec, live voice call with the created agent. Time-box Phase 0 to 20 minutes.

## Git rules
- Initialise nothing: the repo already exists on branch `main`.
- Commit locally after each phase and after any meaningful fix.
- Commit messages: plain, imperative, one line, under 72 characters (for example `Add Gnani gateway with rate limiter`). No trailers of any kind: no `Co-authored-by`, no `Signed-off-by`, no tool or assistant attribution.
- Never run `git push`. Never add or change remotes. Never change git config. Never rewrite history or force anything.
- Do not commit `.env`, audio files, SQLite databases, caches or `node_modules`.

## Gnani rules
- Hatch never calls api.inya.ai and never claims deployment on Gnani Agent Builder. Agents run on the Hatch runtime, using Prisma for speech in and Timbre for speech out.
- All Gnani traffic goes through one gateway with a concurrency limiter, retry, cost ledger and TTS cache. Test agents in text mode so tests cost no Gnani credits.
- Credits are finite (about Rs 5,000 total). Keep a hard stop at the budget in `CREDIT_BUDGET_INR`.
- Synthetic data only. No real personal data anywhere.

## Quality bar
- Write tests for the compiler stages, gateway, lint and runtime. `python scripts/test.py` must pass.
- Real failure paths: Gnani 429/5xx/402/403, LLM invalid JSON, mic denied, ffmpeg missing. The UI shows each one and falls back to text.
- The UI should look finished: clear spec view with provenance badges, test report, live call panel with transcript, latency and cost.
- README must be accurate: what runs, how to start (`python scripts/dev.py`), limitations, models used (Gnani Prisma and Timbre, plus the third-party LLM). Include a section titled "How this was built" containing only a TODO line for the repository owner to fill in. Do not write it for them.

## Review bundle
At the end of each phase write `review/phase_N/` as specified in `docs/04_EVAL_DEMO_RISKS.md` section 5: STATUS.md, `git log --oneline -30`, test and smoke output with secrets redacted, real stack traces, and for later phases three compiled specs, one TestReport and the telemetry table.
