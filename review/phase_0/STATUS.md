# Phase 0 status

- Scaffolding: DONE (verified by: repository file inspection; package manifests, backend, frontend and scripts added).
- Python and Node toolchain: DONE (verified by: `python --version`, `node --version`, `npm --version`).
- ffmpeg: DONE (verified by: bundled ffmpeg version check, v9.0.2; winget was unavailable due network error).
- Gnani API probe: DONE (verified by: `python scripts/probe_gnani.py`; serial STT/TTS calls succeeded for v2.5 and v3.0).
- LLM API probe: DONE (verified by: `python scripts/probe_gnani.py`; configured chat completions returned HTTP 200).
- Rate-limit/concurrency probing: NOT DONE (deliberate load excluded; limits remain unknown).
- Credit cost calibration: NOT DONE (dashboard before/after balances unavailable).
- Frontend build: DONE (verified by: `npm run build --prefix frontend`).
- Backend health test: DONE (verified by: `python -m pytest -q`, 1 passed).
- Frontend/backend startup: DONE (verified by: `python scripts/dev.py`; API health and UI returned HTTP 200).
- Voice API smoke: DONE (verified by: `python scripts/smoke.py`; one real Timbre v3.0 synthesis and Prisma v3.0 transcription succeeded).
