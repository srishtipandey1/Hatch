# Phase 2 status — compiler and runtime

- Requirement extraction, language negotiation, generated copy, validation, provenance, lint, and persistence: DONE (verified by: real API compile on 2026-11-15; spec `spec-hinglish.json`; `python scripts/test.py`).
- Hinglish language policy: DONE (verified by: `spec-hinglish.json` contains `hi-IN` and `en-IN`; provenance fields are present).
- Legacy stored-spec loading and missing-provenance reporting: DONE (verified by: `python scripts/test.py`; legacy specs load with explicit defaulted provenance).
- Create/inspect interface and live agent page: DONE (verified by: Playwright snapshots and screenshots in this folder).
- Text conversation with synthetic order lookup: DONE (verified by: Playwright text turn returned the declared `ORD-1004` delayed status and two-day ETA).
- Full created-agent voice conversation: PARTIAL (voice UI and route exist, but the live speech path is gated while unit rates are uncalibrated; physical microphone input was not tested).
- Three representative compiled specs: DONE (files in this folder; two older specs explicitly mark provenance absent from their original records as defaulted).
