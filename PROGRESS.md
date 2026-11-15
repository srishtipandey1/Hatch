# Progress

## 2026-11-15 11:48 IST

- Phase 0: scaffolding and toolchain check in progress.
- Phase 0: credentials are present by variable name only; their values are not displayed.
- Phase 0: Python 3.11.9, Node 22.15.1, npm 10.9.2 available; ffmpeg missing at initial check.
- Phase 0: live Gnani rate-limit/concurrency load probes are deliberately excluded; do not generate traffic to trigger service limits. API checks, if run, are serial and minimal.
- Cost per unit remains unmeasured because dashboard balances were not supplied.

## 2026-11-15 11:53 IST

- Phase 0: DONE (verified by: `python scripts/probe_gnani.py`; tested Timbre v2.5/v3.0, Prisma v2.5/v3.0 and LLM returned HTTP 200; see `docs/VERIFIED_GNANI.md`).
- Phase 0: frontend production build passed with `npm run build --prefix frontend`.
- Phase 0: FastAPI health test passed with `python -m pytest -q` (1 passed).
- Phase 0: ffmpeg works via bundled `imageio-ffmpeg` (winget download failed; fallback binary verified as version 9.0.2).
- Phase 0: cost remains unmeasured; provider rate-limit/concurrency tests intentionally omitted.
- Phase 0: dev launcher served API health and frontend HTTP 200; one real Timbre v3.0 → Prisma v3.0 smoke round trip returned HTTP 200.

## 2026-11-15 12:42 IST

- Phase 1: implemented the single Gnani gateway, serial priority queue, bounded provider retries, TTS cache, ledger, WebM-to-WAV conversion, and browser push-to-talk/text fallback.
- Phase 1 verification: prior session observed a 6.171-second real synthetic TTS-to-STT echo round trip; live microphone hardware was not exercised.
- Phase 2: real Hinglish compile saved to `review/phase_2/spec-hinglish.json`; `hi-IN` and `en-IN` were selected and all top-level spec fields have provenance.
- Phase 2: browser live page and synthetic `ORD-1004` lookup verified; legacy stored specs now mark unrecorded provenance explicitly.
- Phase 3: six text scenarios completed; one repair round improved the result from 5/6 to 6/6. Report and UI screenshot are in `review/phase_3/`.
- Phase 3: the OpenAI-compatible provider required lowercase `json` in messages and later returned 429; fixed the JSON-mode prompt and added bounded retries honoring `Retry-After`.
- Phase 4: 27 backend tests and the frontend production build passed.
- Safety decision: actual STT/TTS rates remain unknown, so uncached Gnani speech calls now fail closed with HTTP 402 until measured rates are set in `.env`. The clean smoke command confirms this.
- Remaining PARTIAL/NOT DONE: microphone rehearsal, calibrated cost and live voice-agent turn, 10–12 scenario suite, human judge spot-check, demo recording, and submission assets.

## 2026-11-15 14:05 IST

- Phase 5 UI: replaced the page with a single flow (speak or type → compile with live stage timing → provenance-badged spec → 7-caller report and repair diff → live `/a/<id>` page with chat, push-to-talk, text fallback, latency/cost strip, and handoff banner). `npm run build --prefix frontend` passes.
- Voice path: real webm → ffmpeg → Prisma v3.0 returned Hindi and English transcripts; synthetic Timbre → Prisma → LLM → Timbre completed three live turns (Hindi order lookup, English angry caller, English handoff). See `review/phase_final/`.
- Cost: replaced fail-closed speech with conservative planning estimates (STT 0.05 INR/s, TTS 0.50 INR/1000 chars) and kept the 70% budget guard. The UI shows ledger calls and estimated INR; `docs/CREDITS.md` marks the rates as estimates.
- Verification: `python scripts/test.py` → 31 passed; `python scripts/smoke.py` → TTS 200, STT 200, `prisma-v3.0`; backend `/api/health` ok; frontend dev server HTTP 200.
- Not verified: physical microphone hardware, browser audio playback by a human, and a Playwright walkthrough (no browser automation tool in this environment). The demo rehearsal must still be run by the presenter.
