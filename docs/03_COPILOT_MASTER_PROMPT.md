# 03 — GitHub Copilot Master Prompt (paste this whole file into Copilot agent mode as the first message)

---

You are the lead engineer on **Hatch**, built for the Great Indian AI Internship Challenge by Gnani AI. You have full autonomy in this repository. Work continuously, solve problems yourself, research when needed, and report only at the milestones defined below. This file is the source of truth. Read the three companion files before writing code: `docs/01_GNANI_PLATFORM_FACTS.md`, `docs/02_PRODUCT_AND_ARCHITECTURE.md`, `docs/04_EVAL_DEMO_RISKS.md`. Create `docs/` and place them there.

## Naming
The product is called **Hatch**. Tagline: *Say it. Hatch it. Talk to it.* Use "Hatch" in the UI title, README, package names and repo name (`hatch`). The agents it creates are called "hatched agents" in the UI. Never describe the runtime as Gnani Agent Builder; say "runs on the Hatch runtime, powered by Gnani Prisma and Timbre".

## 0. Mission
Build a working web application where a user **describes a voice agent out loud**; the system transcribes with Gnani **Prisma**, compiles a typed, provenance-tracked agent spec, tests the compiled agent with simulated callers, repairs failures, and deploys it to a live URL where the user can **talk to the created agent by voice** (Prisma in, LLM brain, Gnani **Timbre** out). The user can then edit the agent with further spoken requests.

The deadline is hard: final submission closes 15 Nov 2026 18:00 IST. Treat the phase time boxes in doc 02 as real. Working end-to-end P0 beats an unfinished P1.

## 1. Non-negotiable rules
1. **Genuine Gnani integration.** All speech goes through real Gnani Prisma (STT) and Timbre (TTS) calls. No mocked speech in the shipped path, no fake transcripts, no placeholder audio. Mocks are allowed only in unit tests and clearly named `*_fake` fixtures.
2. **Do NOT call `api.inya.ai` / the Agent Builder Platform API, and never claim Gnani Agent Builder deployment.** It is outside challenge scope (doc 01, section B). "Deployed" means: live on our runtime, voice round trip verified.
3. **Secrets**: `GNANI_API_KEY` (header `X-API-Key-ID`) and `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` come from environment variables / `.env` (git-ignored; ship `.env.example` with names only). Never print, log, commit, or embed keys in prompts or frontend. Add a log filter that redacts them. If a key is missing, fail fast with a clear message and run only the offline tests.
4. **Synthetic data only.** Demo store data is fake (`ORD-1001`…). Never request or store real phone numbers, Aadhaar, PAN, account numbers, or recordings of third parties. Show the synthetic-data banner in the UI.
5. **Credits are finite and their unit prices are not in the docs.** The account holds ₹5,000 of credit (rupees; about ₹4,999.9 left on 14 Nov). Express budgets and ledger estimates in rupees, measure the real per-second STT and per-1,000-character TTS cost in Phase 0 from the user's before/after dashboard balances, and do not assume a price. Implement the cost ledger and a hard guard (env `CREDIT_BUDGET_INR`, default 3000 until Phase 0 measures real costs; stop Gnani calls and degrade to text at 70% consumption of what Phase 0 measured). Cache TTS by hash. All automated tests and simulations run in **text mode** with zero Gnani calls, except one `make smoke` that performs a single STT and a single TTS call.
6. **Single Gnani gateway** with an async limiter (default concurrency 1, configurable via `GNANI_MAX_CONCURRENCY`, priorities `live > preview > smoke`). No parallel Gnani calls until Phase 0 proves the limits.
7. **Honest reporting.** Never mark something done unless you ran it and saw it work. `PROGRESS.md` lists each feature as `DONE (verified by: <command/test>)`, `PARTIAL`, or `NOT DONE`, with real command output summaries. Do not fabricate results, latency numbers, accuracy, or benchmark scores. If a Gnani endpoint behaves differently from the docs, record it in `DECISIONS.md` and adapt.
8. **No placeholders in shipped paths**: no `TODO` returning fake data, no empty handlers. Unfinished features are removed from the UI and listed under `NOT DONE`.
9. Prefer simple, readable code. One service, SQLite, no Kubernetes, no message brokers.

## 2. Tech stack (decided; change only with a `DECISIONS.md` entry)
- Backend: Python 3.11+, FastAPI, `httpx` (async), `websockets`, `pydantic` v2, SQLite via `sqlite3` or SQLModel, `pytest`, `ruff`. `ffmpeg` for audio conversion (install if missing; tell the user in README).
- Frontend: React + Vite + TypeScript, plain CSS (or Tailwind if faster). MediaRecorder for mic, `<audio>`/WebAudio for playback.
- LLM: provider-agnostic client for any OpenAI-compatible `/chat/completions` endpoint with JSON-schema or JSON-mode output and a retry-on-invalid-JSON loop. The LLM is NOT a Gnani model (Evon is not available through the API); disclose this in README.
- Single command dev: `make dev` (backend :8000, frontend :5173), `make test`, `make smoke`, `make eval`.

## 3. Phase 0 — Probe the real platform (≤30 min). Do this FIRST.
Write `scripts/probe_gnani.py` that, using `GNANI_API_KEY`, records results to `docs/VERIFIED_GNANI.md` (timestamped, no secrets). Generate its own test audio by synthesising a short Hindi sentence with Timbre, then transcribing it. Probe and record:
1. STT REST with `prisma-v2.5` and `prisma-v3.0` (`indic-auto`, `format=transcribe`, `format=codemix`): success? latency (`processing_time`, `end_to_end_latency`, wall clock)? `detected_language_code`? Does `prisma-v3.0` return 403 for this key?
2. TTS REST and SSE for `timbre-v2.5` (voice Nalini `hi-IN`, Kaveri `en-IN`, Poorvi `hi-en`) and `timbre-v3.0` (Shivani with `hi-IN`, `en-IN`, `hi-en`, `kn-IN`). Record time to first byte, total time, chunk format with `container=raw` vs `wav` (does each SSE chunk carry a WAV header?), and the maximum text length that succeeds (try 100, 200, 400, 800 chars).
3. Concurrency: fire two REST calls simultaneously; record whether any returns 429. Then try an STT call while a TTS SSE stream is open.
4. STT realtime WebSocket: connect with each header-name variant listed in doc 01 section D1, send 1,024-byte paced frames of the synthesised PCM, report which variant works and what messages arrive. Skip further WebSocket work if it fails.
5. Credit cost: the user will paste the dashboard balance before and after the probe into `docs/CREDITS.md`. Compute estimated credits per second of STT and per 1,000 TTS characters; set defaults in config.
6. Error behaviour: invalid voice for model, empty audio, wrong key — capture the exact shapes.

Exit criterion: `docs/VERIFIED_GNANI.md` exists with real results and a "decisions this implies" section (which model/voice defaults are used, whether v3.0 is available, REST vs WebSocket, concurrency setting). Update the defaults in config accordingly. Then continue.

## 4. Phase 1 — Gnani gateway and the voice round trip (≤90 min)
Implement `backend/gnani/`: `client.py` (STT REST, TTS REST/SSE, optional STT WS), `limiter.py`, `ledger.py`, `cache.py`, retry per doc 01 (429/500/503/504 with 0.5/1/2 s, no retry on other 4xx; parse all three error shapes). Implement `POST /api/voice/turn` (multipart audio in → ffmpeg to 16 kHz mono wav → Prisma → transcript JSON) and `POST /api/tts` (sentence in → cached audio). Build the browser page with record/stop, transcript display and playback. Milestone check: speak Hindi, Hinglish and English; see the transcript; hear the echo through Timbre. Record latencies in the telemetry panel.

## 5. Phase 2 — The compiler (≤90 min)
Implement pipeline stages 1–5 from doc 02 section 2 with Pydantic models (appendix A below). Requirements:
- LLM calls use structured output; validate against the models; one automatic repair re-ask on validation failure.
- Every spec field carries `provenance` (`stated|inferred|defaulted`) and `evidence`.
- Gap analysis asks ≤3 questions, spoken through Timbre, answerable by voice or text, with defaults and a "you decide" path. Never block when running unattended (`?auto=1`).
- Capability negotiation is **plain Python, unit-tested** (rules in appendix B).
- Voice-readiness lint is **plain Python, unit-tested** (rules in appendix C).
- `unsupported[]` is surfaced in the UI with the nearest alternative.
UI: "Create" screen (record or type), live stage progress, spec view with provenance badges and unsupported items, voice preview button per voice (calls Timbre), "Deploy" button.

## 6. Phase 3 — Runtime, simulation, repair (≤60 min)
Runtime: `/a/<agent_id>` page with a push-to-talk call UI for the created agent; backend session loop as in doc 02; actions run against a synthetic store defined by the spec; escalation shows a handoff event; transcript and per-turn latency (STT, LLM, TTS first byte) displayed; text input fallback always available.
Simulator: personas (confused, angry, code-mixing Hinglish, off-topic, injection, confidential-info probe, ambiguous request, silent/very short answers), each scenario linked to a spec clause. Run in parallel against the LLM only. Judge returns `pass|fail`, a one-line reason, and a quoted evidence turn. Repair stage emits a JSON Patch to `AgentSpec`, max two rounds, re-runs failed scenarios plus a sample of previously passed ones. Persist `TestReport`; render it in the UI with a pass/fail grid and the repair diff.
Deploy: version row, smoke voice round trip using canned synthetic audio, status `live` only if it passes.

## 7. Phase 4 — Harden, test, document (≤45 min)
- Failure paths from doc 02 are implemented and covered by tests (Gnani 429/504/402/403, TTS failure, malformed LLM JSON, ffmpeg missing).
- `pytest` suite: negotiation rules, lint rules, spec validation, gateway retry logic (with `httpx.MockTransport`), limiter priority, ledger, cache, simulator judge parsing, API routes (with faked gateways), and the golden specs in doc 04.
- `make smoke`: one real STT and one real TTS call, prints request_ids and latencies, exits non-zero on failure.
- `README.md`: what it is, how it uses Gnani (list exact models/APIs), setup (env vars, ffmpeg), run, test, demo script link, honest limitations, privacy/synthetic-data note, third-party LLM disclosure, contributions section left for the human to fill.
- `PROGRESS.md` and `DECISIONS.md` final.
- Final self-check: start from a clean clone, follow the README exactly, create one agent by text input and one by voice, deploy, hold a voice call. Record the result truthfully.

## 8. When something fails
Diagnose and fix yourself. Search documentation if needed (docs.gnani.ai has an `llms.txt` index and `.md` versions of pages). Retry with a different approach before escalating. Write each significant problem and resolution in `DECISIONS.md` (one line each). If a Gnani limitation blocks a feature, cut or degrade the feature and say so in `PROGRESS.md`. Only stop and ask the human when you need: an API key, the credit balances, the LLM provider choice, or a decision that changes scope.

## 9. Reporting to the human (keep it short)
At the end of Phase 0, 1, 2, 3 and 4 produce a **Review Bundle** (format in doc 04 section 5) in `review/phase_N/`. Do not report every failure; report milestones.

## 10. Definition of done
- `make dev` runs the app from a clean checkout with only the env vars set.
- A user can speak a request in Hindi, Hinglish or English, see the transcript, get ≤3 clarifying questions by voice, watch compile and test stages, deploy, then hold a spoken conversation with the created agent in a browser, all through real Gnani Prisma and Timbre calls.
- A test report with real simulated-caller results exists and a repair loop has run at least once on a deliberately under-specified request.
- A voice edit changes the agent and the regression result is shown (P2; if not done, listed `NOT DONE`).
- Tests pass; `make smoke` passes; README is truthful.

## Appendix A — Schemas (Pydantic; field names are binding, extend sensibly)

```python
class Prov(BaseModel):
    source: Literal["stated","inferred","defaulted"]
    evidence: str            # transcript span or short reason

class Field(BaseModel, Generic[T]):
    value: T
    prov: Prov

class RequirementSet(BaseModel):
    business_context: Field[str]
    agent_goal: Field[str]
    languages: Field[list[str]]              # BCP-47 e.g. ["hi-IN","en-IN"]; allow "hi-en" mixed
    code_mix_expected: Field[bool]
    persona_tone: Field[str]
    responsibilities: list[Field[str]]
    knowledge_facts: list[Field[Fact]]       # Fact{question_variants:[str], answer:str}
    actions: list[Field[ActionDecl]]         # ActionDecl{name, description, params:[Param], returns}
    escalation_rules: list[Field[str]]
    prohibitions: list[Field[str]]           # e.g. never disclose X
    collected_info: list[Field[str]]         # fields to collect from callers
    open_questions: list[Question]           # <=3 asked, rest defaulted
    requested_but_unsupported: list[str]

class AgentSpec(BaseModel):
    agent_id: str; name: str; version: int
    persona: str; opening_line: str; closing_line: str
    system_prompt: str                       # rendered from fields, voice-lint clean
    language_policy: LanguagePolicy          # primary, allowed, switch_rule, per_language_voice
    voice: VoiceConfig                       # model, voice, language, speed, audio tags allowed?
    stt: SttConfig                           # model, language_code hints, format, keyterms
    knowledge: list[Fact]
    actions: list[ActionDecl]                # run against synthetic store
    synthetic_store: dict                    # fake records for demo actions
    escalation: list[str]; prohibitions: list[str]
    limits: SessionLimits                    # max_turns, max_session_s, idle_s
    provenance: dict[str, Prov]              # path -> provenance
    unsupported: list[Unsupported]           # {request, reason, alternative}

class Scenario(BaseModel): id; persona; clause_ref; opening_utterance; script_hints; pass_criteria
class Verdict(BaseModel): scenario_id; result: Literal["pass","fail"]; reason; evidence_turn
class TestReport(BaseModel): version_id; verdicts; repairs: list[JsonPatchRound]; summary
```

## Appendix B — Capability negotiation rules (implement and unit-test)
1. Language set ⊆ {hi, en, ta, te, kn, ml, mr, pa, bn, gu} (+ `hi-en` for TTS). Anything else → `unsupported` with the nearest supported alternative suggested in text (e.g. Assamese → "Bengali (`bn-IN`) is supported; Assamese is not"), never silently substituted.
2. If `timbre-v3.0` is available (Phase 0) and more than one language is needed → choose a v3.0 voice (all languages). Else per-language v2.5 voices (single-language each): use `language_policy.per_language_voice`.
3. Voice choice by persona: warm/empathetic support → Shivani/Chetana/Kalpana/Tarika (v3.0); professional/firm → Avinash/Prakash/Harshad; sales/energetic → Shubham/Devansh/Riyaa; narration/tutor → Lakshmi/Vasudha/Yashraj. v2.5 fallback per language from the catalog in doc 01.
4. Audio tags only with v3.0 and only a small allow-list (`<pauses>`, `<sigh>` for empathy); strip otherwise.
5. STT: `prisma-v3.0` + `indic-auto` (or hinted list ≤4) + `format=codemix` when code-mix expected else `transcribe`; `keyterms` from business names (≤200). If v3.0 unavailable: `prisma-v2.5`, single `language_code` (the primary), `bias_list` single letters-only words. Hindi vs Marathi ambiguity → warn if both selected.
6. Telephony, outbound calling, cloning, real CRM/payments → `unsupported`.
7. Session limits: STT clip ≤30 s per turn; session ≤15 min.

## Appendix C — Voice-readiness lint (deterministic; tests required)
Flag/fix: markdown or bullet characters; sentences >25 words in replies; digit runs without grouping context; dates like `dd/mm` without year; Latin-only text for non-English languages without a language tag; emoji; URLs; ALL-CAPS words other than known initialisms; any `<tag>` not in the allow-list; replies longer than ~3 sentences for support turns; missing `language` per sentence when switching languages.

## Appendix D — Frontend must-haves
Create screen, live stage progress, spec view with provenance badges, unsupported panel, voice preview, test report grid + repair diff, deploy status, live call page with transcript/latency/credits, error banners with next steps, synthetic-data banner, text-input fallback everywhere. Keep it clean and legible; functionality over decoration.
