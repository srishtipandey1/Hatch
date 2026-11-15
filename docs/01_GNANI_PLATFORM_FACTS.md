# 01 — Gnani Platform Facts (verified 14 Nov 2026) and Access Matrix

Everything in section A–D was read from the primary pages listed in section G on 14 Nov 2026. Anything not read from a primary page is in section E ("must be measured") and is NOT to be assumed. Copilot: re-verify against live docs in Phase 0 and write the results to `docs/VERIFIED_GNANI.md`; where reality disagrees with this file, reality wins and the discrepancy goes into `DECISIONS.md`.

## A. Challenge rules that constrain the design (gnani.ai/internship, registration terms)

- Deadline: **15 Nov 2026, 18:00 IST, final, no extensions** (official page and terms). Some press says 10 Nov; that is stale.
- Required: a working app using at least one Gnani model/API; public demo video; post on LinkedIn or X with `#GnaniAI #GreatIndianAIInternshipChallenge` and tag Gnani's account; the post must be live **before** submitting; written explanation; list of Gnani models/APIs used; each member's contribution.
- Shortlisting is driven by **verified engagement on the nominated post recorded by the closing cutoff**, plus eligibility/genuine-use checks. Post early.
- Credits: **₹5,000 of complimentary credit (rupees), confirmed by the account welcome email of 6 Nov; about ₹4,999.9 remained on 14 Nov** (user's own test spend ≈ ₹0.1). One pool covers STT, TTS and voice cloning across 10 Indic languages and English, usable via the dashboard `app.gnani.ai/voice` playground and API keys. Per-unit prices are NOT published in the docs I read; a third-party reseller lists Prisma v2.5 at about ₹27 per audio hour, which is unofficial and must be re-measured in Phase 0. If that figure is anywhere near right, the pool is ample for this project, so the earlier "credits are scarce" assumption is relaxed but the ledger and guard stay. Voice cloning is covered by the credit email but is not in the challenge's listed models; still not used in P0/P1.
- **Agent Builder is out of scope, and Gnani states it offers no participant APIs for it.** Evon v3.3 is not on the API platform; it is open weights (gated, "by request") on Hugging Face.
- Data: use synthetic data only. No real phone numbers, account numbers, Aadhaar, PAN, or recorded calls of other people.
- Authenticity: no bought engagement, bots, paid promotion, engagement swaps, plagiarism, or misleading demos.

## B. Access matrix — four separate questions

| Capability | Publicly documented | Technically accessible | Available to the participant account | Permitted by the challenge |
|---|---|---|---|---|
| Prisma v2.5 STT (REST, WebSocket, Batch) | Yes | Yes, `api.vachana.ai`, header `X-API-Key-ID` | Yes (credits apply per official page) | Yes, explicitly |
| Prisma v3.0 STT (`model=prisma-v3.0`, released 22 Oct 2026) | Yes | Expected yes | **Unverified** (key scopes can return 403 `SCOPE_NOT_ALLOWED`) | Almost certainly (same family) |
| Timbre v2.5 TTS (REST, SSE, WebSocket) | Yes | Yes | Yes (listed as beta) | Yes, explicitly |
| Timbre v3.0 TTS (13 voices, all 10 languages, audio tags) | Yes | Expected yes | **Unverified** | Almost certainly |
| Voice cloning (`vachana-vc-v1`) | Yes | Expected yes | **Unverified** | **Unclear** (not in the challenge's listed models). Do not use in P0/P1. Never clone anyone but the builder, with consent |
| Evon v3.3 | Model card + release notes | Only by self-hosting gated weights | No API access | Yes, but needs a GPU node; out of scope for one day |
| Agent Builder (Inya dashboard) | Yes | Separate product login | No | **No — explicitly out of scope** |
| Agent Builder Platform API (`https://api.inya.ai/platform`, header `x-api-key`, scopes `agents`, `conversations`; create/update agent, FAQs, validate prompt, trigger test call, conversation logs, chat widget) | Yes (docs "last verified 11 Aug 2026") | Only with an Inya Agent Builder API key, which is a different credential from the programme's `app.gnani.ai/voice` key | **No**, per the official FAQ ("we don't offer APIs for it yet") | **No — outside scope** |

**Resolution.** The docs and the FAQ disagree on the Platform API. For this challenge the FAQ controls. Decision: the product does **not** call `api.inya.ai`, does not attempt to use programme credentials against it, and does not claim "deployed to Gnani Agent Builder". Hatch builds its own agent runtime on Prisma + Timbre. As an optional P2 feature the compiler may emit an `inya_export.json` file shaped like the documented Update Agent schema, labelled "export only, not deployed, requires Agent Builder access". No network call.

**Question to send on Gnani's Discord (the official channel) today** — copy verbatim:

> Hi Gnani team, for the Great Indian AI Internship Challenge: the FAQ says Agent Builder is out of scope with no participant APIs, while docs.gnani.ai lists an Agent Builder Platform API at api.inya.ai. We are NOT using it; we're building our own agent runtime on Prisma + Timbre. Could you confirm: (1) our account's request-rate and concurrent-session limits (the docs say numbers are on app.gnani.ai), (2) credit cost per second of STT and per character of TTS, (3) whether prisma-v3.0 and timbre-v3.0 are enabled for programme keys, (4) whether using a third-party LLM for reasoning alongside Prisma/Timbre is acceptable for the "genuine use" check. Thanks!

## C. Verified API contracts

Base for speech: `https://api.vachana.ai`. Auth header on every call: `X-API-Key-ID: <key>`. (Python SDK `pip install gnani-vachana`, Python ≥3.10, clients `GnaniSTTClient`, `GnaniSTTStreamClient`, `GnaniTTSClient`, `GnaniTTSStreamClient`, `GnaniTTSRealtimeClient`; also `livekit-plugins-gnani` and a Pipecat plugin exist.) Prefer plain `httpx`/`websockets` in the backend so behaviour is observable and controllable; the SDK is acceptable if it proves simpler.

### STT REST — `POST /stt/v3`, multipart/form-data
- Fields: `audio_file` (wav, mp3, ogg, flac, aac, m4a; **max 30 s**; <0.1 s returns empty transcript), `language_code` (required except with `format=transliterate`), optional `model` (`prisma-v3.0`; omit for v2.5), `format`, `keyterms`, `topic`, `previous_text`, `speaker_names` (all v3.0-only), `enable_substitution` + `substitution_map` (≤10 rules), v2.5-only `bias_list` + `bias_score` (0, 0.5, 1.0, 1.5, 2.0), `itn_native_numerals` (no effect on v3.0). Optional header `X-API-Request-ID`.
- Languages: `bn-IN en-IN gu-IN hi-IN kn-IN ml-IN mr-IN pa-IN ta-IN te-IN`. v3.0 also accepts `indic-auto` or a comma list of 1–4 codes such as `hi-IN,en-IN` (hints, not a lock).
- `format`: `verbatim` | `transcribe` (digits/currency) | `codemix` (v3.0; English stays Latin, numbers mostly words) | `transliterate` (v3.0; Latin letters only; `language_code` optional). With v3.0, omitting `format` gives `transcribe` for a single `hi-IN`/`en-IN` and `verbatim` otherwise. **Always send `format` explicitly.**
- Success: `{success, request_id, transcript, model, detected_language_code?, processing_time, end_to_end_latency, truncated?}` (v2.5 also has `output.literal`). Empty transcript is not an error.
- Errors: `{"success":false,"error":{"type","message"}}` for STT business errors; `422 {"detail":[...]}` for missing fields; auth/rate errors use `{"detail":{"error_code","message","status_code"}}` with `MISSING_API_KEY` 401, `INVALID_API_KEY` 401, `402` insufficient credit (not fully verified), `SCOPE_NOT_ALLOWED` 403, `RATE_LIMITED` 429; v3.0 can return `504 UPSTREAM_TIMEOUT` (5000 ms transcription bound). Retry 429/500/503/504 with backoff 0.5/1/2 s, three attempts; do not retry other 4xx.

### STT Realtime — `wss://api.vachana.ai/stt/v3/stream`
- Config via **WebSocket upgrade headers**: `x-api-key-id`, `lang_code`, `x-sample-rate` (8000/16000/44100/48000, default 16000), `x-format`, VAD headers `x-vad-threshold` (0.7), `x-min-silence-ms` (500), `x-min-speech-ms`, `x-min-segment-ms`, `x-max-speech-s`, optional `x-idle-timeout-sec` (5–900, default 60). Browsers cannot set these headers: **proxy through the backend**.
- Send **binary PCM s16le mono frames of exactly 1,024 bytes, at real-time cadence** (32 ms per frame at 16 kHz). Do not burst. For 44.1/48 kHz the server resamples but the frame size stays 1,024 bytes.
- Server JSON messages: `connected`, `processing` (VAD end-of-speech), `transcript` (`text`, `audio_duration_ms`, `segment_id`, `segment_index`, `latency` ms), `error`, `settings_updated`. There is no token-level partial transcript (a `x-partials` header is mentioned once in docs but undocumented; do not rely on it).
- Client control frame: `{"type":"update_settings", ...}` for substitution/bias (and `format` on v3.0 per its page). Client `{"type":"commit"}` appears in the quick-start example.
- Session cap 15 min; idle timeout 60 s; a per-organisation concurrent-session cap exists and rejects with an `error` message. Bad handshake header closes with 1008; over-length session closes with 1001.

### TTS — Timbre
- REST `POST /api/v1/tts/inference` (binary audio), SSE `POST /api/v1/tts/sse` (events `start`, `chunk` with base64 `audio` and `chunk_index`, `complete`, `error`), WebSocket `wss://api.vachana.ai/api/v1/tts` (send one JSON request at a time; server sends `start`, `audio` messages with `data.audio` base64 and `data.chunk_index`, then `complete`).
- Body: `text`, `voice`, `model` (`timbre-v2.5` | `timbre-v3.0`), `language` (`auto`, `hi-IN`, `en-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `pa-IN`, `bn-IN`, `gu-IN`, `hi-en`), `speed` (0.85–1.15 or `slow|medium|fast`), `audio_config` {`sample_rate` ∈ 8000/16000/22050/24000/44100/48000, `num_channels`, `sample_width`, `encoding` ∈ linear_pcm/pcm_s16le/pcm_mulaw/pcm_alaw/oggopus, `container` ∈ wav/raw/mp3/ogg/mulaw/alaw, `bitrate` for mp3}. OGG/Opus is delivered as one chunk after synthesis (no streaming). mulaw/alaw force 8 kHz.
- **Voices are not interchangeable between models**; a wrong pairing returns 400.
  - Timbre v2.5 (42 voices, each with one preferred language; set `language` to match): English Kaveri, Trupti, Devika, Pranav, Shlok, Girish; Hindi Nalini, Bhavna, Yashvi, Urmila, Jwala, Chitra, Ambuja, Deepak, Roopesh, Vikrant, Hemraj, Jalaj, Omkar; Hinglish (`hi-en`) Poorvi; Tamil Asmita, Trisha, Brinda, Vedika, Noopur; Telugu Suhana, Lehara, Lavanya, Yukti, Varuni; Kannada Saanvi, Kavin; Malayalam Reshma, Riyaan; Marathi Zahira, Ishaan; Bengali Kirra, Dhruva; Gujarati Falak, Veera; Punjabi Mehuli, Zayan.
  - Timbre v3.0 (13 voices, **each speaks all 10 languages**, supports inline audio tags `<pauses> <laugh> <sigh> <whispers> <excited> <slow> <shouting> <coughs> <exhales> <giggle> <sniffles> <yawns> <clears throat>`; v2.5 strips tags): Female Shivani (warm, empathy-first inbound support), Chetana (gentle, healthcare/telecom), Kalpana (composed, care/insurance), Tarika (reassuring, banking care), Lakshmi (expressive, storytelling/e-learning), Vasudha (expressive narration), Riyaa (confident outbound sales). Male Avinash (professional, firm, collections/BFSI), Prakash (steady, BFSI), Harshad (professional, firm), Shubham (energetic sales), Devansh (young conversational, sales/fintech), Yashraj (warm narrative, IVR/e-learning).
- Text normalisation is automatic and good (numbers, ₹ amounts with lakh/crore grouping, dates, times, phone numbers, OTP, IDs, units). Rules that matter: pass `language` explicitly (`auto` treats Latin-only text as English, so a Kannada voice reading "42" needs `kn-IN`); `23/06` reads as a fraction, include the year for dates; digit runs of 6+ are read digit-by-digit (use this deliberately for order numbers, avoid it for quantities by writing words); repeated digits in English IDs may be compressed ("double eight"); Latin-script text needs the language hint.
- Errors for TTS REST/SSE use a flat `{"success":false,"message","status_code"}`; over-long text returns 500 `We are facing technical difficulties`. **Max text length is not documented: chunk to sentences (aim ≤200 characters per request) and measure.**

### Prisma v3.0 behaviours that matter
`detected_language_code` is derived from the script of the transcript (Hindi/Marathi ambiguous on short utterances; mostly-English text with a short native phrase can be tagged `en-IN`). Context can lower accuracy; A/B on your own audio. Romanised output accuracy is explicitly unmeasured. Realtime accepts `keyterms` only among the context fields (per changelog).

## D. Documented discrepancies — treat each as a Phase 0 probe

1. STT realtime header names differ across pages: `lang_code` (stt-websocket page) vs `language_code` and `model` (quick-start) vs `x-model` and `lang_code` (changelog). Probe the variants; record which one works.
2. REST clip limit: 30 s (REST page, limits, errors) vs "≤ 60 s" (intro, realtime page tables). Use 30 s.
3. Quick-start calls Timbre v2.5 "recommended" while the voice catalog and endpoint pages offer Timbre v3.0 as the richer option; the internship page names Timbre v2.5 (beta).
4. Deadline: press 10 Nov vs official 15 Nov 18:00 IST. Official wins.

## E. Unknowns that MUST be measured in Phase 0 (do not guess)

1. Whether programme keys can call `prisma-v3.0` and `timbre-v3.0` (probe; fall back to v2.5 transparently).
2. Rate limits: the docs show an example "only 1 active request allowed at a time". Determine empirically whether (a) two simultaneous REST calls 429, (b) an open STT WebSocket plus a TTS SSE call can run at once, (c) the concurrent WebSocket cap. This decides the interaction mode (see 02).
3. Credit cost: read the dashboard balance before and after N seconds of STT and N characters of TTS and compute credits/second and credits/1,000 characters. Write the numbers down. Set a hard budget guard at 70% of balance.
4. TTS time-to-first-byte and total latency for 40/120/200-character sentences on both models; STT `latency`, `processing_time`, `end_to_end_latency` on 3 s / 10 s / 25 s clips.
5. Max TTS text length; SSE chunk format when `container=raw` (are chunks raw PCM, or does each carry a header?).
6. Whether `language=hi-en` works with Timbre v3.0 voices.
7. Behaviour of a 402/403 when credits run out (so the UI can degrade gracefully).

## F. What this means for the design (decisions already taken)

- No Gnani agent runtime is available to participants, so **we build the runtime**. This is the real opportunity: Hatch's output is a live, voice-callable agent running on our runtime, with Prisma as its ears and Timbre as its voice.
- Concurrency may be 1: design every Gnani call through a single async limiter with a priority queue (live-call traffic first, then Hatch previews, then eval). Never fan out Gnani calls in parallel. LLM-only simulation can be parallel.
- Credits are scarce and unmetered in docs: cache TTS audio by hash(model, voice, language, speed, text); run all automated agent tests in text mode; spend voice credits only on the live demo path and a small smoke test.
- Evon is not usable as an API. The LLM layer is provider-agnostic (see 02). Disclose the third-party LLM in the submission.

## G. Sources (primary)

- https://www.gnani.ai/internship (rules, FAQ, deadline, awards)
- https://www.gnani.ai/great-indian-ai-internship-registration-form (terms)
- https://docs.gnani.ai/llms.txt (full doc index, 14 Nov 2026)
- https://docs.gnani.ai/api/introduction/quick-start.md
- https://docs.gnani.ai/api/STT/speech-to-text.md, https://docs.gnani.ai/api/STT/stt-websocket.md, https://docs.gnani.ai/api/STT/limits.md, https://docs.gnani.ai/api/STT/models/prisma-v3.md
- https://docs.gnani.ai/api/TTS/tts-inference.md, tts-sse.md, tts-websocket.md, available-voices.md, tts-input-formating.md
- https://docs.gnani.ai/api/introduction/errors.md, https://docs.gnani.ai/api/introduction/changelog.md
- https://docs.gnani.ai/Platform/platform-introduction.md, Create_Agent.md, Update_Agent.md (Platform API — documented, NOT used)
- https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B (Evon weights, gated)
- https://pypi.org/project/livekit-plugins-gnani/ (plugin; confirms voices and `api.vachana.ai`)
