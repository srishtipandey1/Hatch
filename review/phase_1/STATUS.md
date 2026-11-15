# Phase 1 status — speech gateway

- Gnani gateway, priority limiter, retry handling, SQLite ledger, and TTS cache: DONE (verified by: `python scripts/test.py`).
- Prisma/Timbre model access: DONE (verified by: `python scripts/probe_gnani.py`; serial v2.5/v3.0 probes are recorded in `docs/VERIFIED_GNANI.md`).
- WebM/WAV normalization to 16 kHz mono: DONE (verified by: `python scripts/test.py`, including a generated WebM conversion).
- Echo voice round trip: PARTIAL. A prior session observed a real TTS → WAV → STT round trip at 6.171 seconds. The current clean smoke check is intentionally blocked because actual STT/TTS prices remain uncalibrated.
- Browser push-to-talk implementation: PARTIAL (the getUserMedia/MediaRecorder path is implemented; physical microphone capture and permission denial were not exercised).
- Credit ledger: DONE (verified by: `python scripts/test.py`); calibration is PARTIAL because provider charges were not available. The runtime fails closed for unpriced uncached speech calls.
- Provider concurrency/rate-limit load probing: NOT DONE (deliberately excluded; account limits remain unknown).

Current smoke behavior: `python scripts/smoke.py` returns HTTP 402 `COST_UNCALIBRATED` until measured rates are entered in `.env`. See `docs/CREDITS.md`.
