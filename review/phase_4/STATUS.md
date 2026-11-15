# Phase 4 status — hardening and handoff

- README setup, models, limitations, and owner-only “How this was built” TODO: DONE (verified by: README inspection).
- Backend tests: DONE (verified by: `python scripts/test.py`, 27 passed).
- Frontend type-check and production build: DONE (verified by: `npm run build --prefix frontend`).
- Failure UI for unpriced speech: DONE (verified by: HTTP 402 and `phase_3/cost-guard-error.png`).
- LLM JSON-mode, rate-limit, and provider error handling: DONE (verified by: focused tests; a real text-mode simulation completed after honoring retry timing).
- FFmpeg-missing fallback: DONE (verified by: `python scripts/test.py`).
- Smoke script uses the local gateway: DONE (verified by: source inspection; it does not bypass the gateway).
- Current real speech smoke: PARTIAL (blocked before an unpriced provider request; set measured rates in `.env` to enable it).
- Physical microphone rehearsal, spoken utterance set, full voice-agent conversation, demo video, and submission post: NOT DONE.
- Clean app startup: DONE (verified by: `python scripts/dev.py`; API health and frontend returned HTTP 200).

Do not claim a completed spoken demo until rates are calibrated and the browser microphone path is rehearsed.
