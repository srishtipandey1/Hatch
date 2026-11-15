# Credit measurements

Dashboard balances were not available to the implementation environment, so no per-unit price has been measured. Instead of blocking speech, Hatch uses conservative planning estimates so the ledger overstates rather than understates spend. Override either rate in `.env` as soon as a measured delta exists.

| Service | Variable | Value used | Basis |
|---|---|---:|---|
| STT | `STT_COST_INR_PER_SECOND` | 0.05 | ~INR 180 per audio hour, deliberately above the only public figure (~INR 27/hour for Prisma v2.5) |
| TTS | `TTS_COST_INR_PER_1000_CHARS` | 0.50 | Planning estimate, not a published rate |

The gateway records every provider attempt in `data/hatch.sqlite3` with model, units, estimated INR, request ID, status and latency. `/api/ledger` and the UI read that ledger. Cached TTS responses are free and are not counted as provider calls.

Speech calls pause with HTTP 402 `LOCAL_BUDGET_GUARD` before estimated spend exceeds 70% of `CREDIT_BUDGET_INR`, leaving a margin for pricing error. Text compilation, simulated callers and the text fallback do not call Gnani and keep working when the guard trips.

To calibrate: record the dashboard balance, make one known-length STT call and one known-length TTS call, then solve for the unit rate and set the variables in `.env`. Restart the backend afterwards.
