# Runtime telemetry snapshot

Source: local SQLite Gnani ledger, grouped by service/model after the serial probes and voice-path checks. Values are raw ledger totals; rupee estimates remain null because rates are uncalibrated.

| Service | Model | Recorded requests | Successful | Average latency (ms) | Units | Estimated INR | Unpriced |
|---|---|---:|---:|---:|---:|---:|---:|
| STT | prisma-v3.0 | 1 | 1 | 256.0 | 3.042 | Unknown | 1 |
| TTS | timbre-v3.0 | 7 | 3 | 2114.1 | 297 | Unknown | 7 |

These are request attempts, not unique user utterances. Provider pricing and account rate limits remain unmeasured. New unpriced speech requests are blocked before reaching Gnani.
