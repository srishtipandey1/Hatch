# 02 — Product and Architecture

Status labels used below: **[V]** verified in docs (see 01), **[A]** assumption to probe, **[O]** original design decision.

## 1. Independent assessment of the idea

**The initial idea as stated is weak in three ways.**
1. "Describe an agent, get a configured agent" is a prompt-to-JSON wrapper. Every voice-agent vendor (including Gnani's own Inya builder) has a version of it. A reviewer who has seen dozens of Prisma+Timbre demos will see a form-filler with a mic.
2. Its "deploy to Gnani" leg is **not available** to participants (01, section B). Building the product around it would fail on demo day.
3. A generated agent that has never been tested is a guess. "Created" is not "works".

**The stronger product: a voice-agent compiler with a test-and-repair loop, and a runtime we own.**

> You describe an agent out loud. Hatch compiles your description into a typed, provenance-tracked agent spec, *attacks the compiled agent with simulated callers*, repairs what breaks, then puts the agent on a live URL you can phone-test by voice in the browser. You then edit it by voice, and every edit is regression-tested before it lands.

What is genuinely different, and checkable by a reviewer:
- **[O] Provenance-tracked spec.** Every field of the spec is tagged `stated` (user said it, with a transcript span), `inferred` (derived, with a reason), or `defaulted` (system choice). The UI shows this. This is the answer to "how do we avoid inventing requirements": invented fields are visible and one-click rejectable.
- **[O] Capability negotiation against Gnani's real constraints.** The compiler knows (from 01) that Timbre v2.5 voices are single-language, v3.0 voices speak all ten, v3.0 supports audio tags, STT REST clips are ≤30 s, `hi-en` is a TTS language value, Hindi/Marathi are ambiguous in `detected_language_code`. Unsupported asks (e.g. "answer real phone calls", "Assamese") produce an explicit `unsupported` entry with the nearest supported alternative rather than silent failure.
- **[O] Voice-readiness lint.** A deterministic pass over the generated prompt and sample replies: no markdown, short sentences, numbers/currency/dates in forms Timbre normalises correctly (01, section C), no `23/06` ambiguity, language tag per sentence, Latin-script-only text routed with an explicit `language`. This is Gnani-specific engineering a generic builder does not have.
- **[O] Adversarial simulation before deploy.** An LLM-driven simulated caller (personas: confused, angry, code-mixing, off-topic, prompt-injecting, asks-for-confidential-info) runs against the compiled agent in text mode, in parallel, costing zero Gnani credits. A judge scores against rubrics derived from the spec itself. Failures trigger a bounded repair step (max 2 rounds) that edits the spec, not the prompt text directly.
- **[O] Honest deployment.** "Deployed" means: the agent is running on our runtime at `/a/<id>`, a browser voice call works end to end through Prisma → LLM → Timbre, and a health check passed. The UI states "runs on Hatch runtime, powered by Gnani Prisma and Timbre". It never claims Gnani Agent Builder deployment.
- **[O] Voice edit with regression.** "Make it more polite and also handle exchanges" → spec patch → previous passing tests re-run → diff shown (what changed, what still passes).

Things deliberately NOT built: multi-agent orchestration inside Hatch (a single compiler pipeline is enough and easier to debug), telephony, voice cloning, RAG over uploaded PDFs, user accounts, payments.

## 2. Architecture

One FastAPI backend (Python 3.11+), one React/Vite frontend, SQLite, local filesystem for audio cache. Deployable as a single container; runs locally with `make dev`.

```
Browser (mic via MediaRecorder / getUserMedia)
   │  HTTPS + WebSocket (our protocol, never exposes Gnani key)
   ▼
FastAPI backend
 ├─ GnaniGateway  ── single async limiter + priority queue + retry + cost ledger + TTS cache
 │     ├─ STT: POST api.vachana.ai/stt/v3  (primary)  /  WS stt/v3/stream (feature-flagged upgrade)
 │     └─ TTS: SSE or REST api.vachana.ai/api/v1/tts/*
 ├─ LLMGateway    ── provider-agnostic (OpenAI-compatible HTTP), JSON-schema constrained output, retries, token ledger
 ├─ Compiler      ── stages 1–6 below
 ├─ Simulator     ── persona caller + target agent + judge (text mode, parallel, LLM only)
 ├─ Runtime       ── executes a compiled AgentSpec for a live voice session (turn loop)
 ├─ Store         ── SQLite: agents, spec versions, test runs, sessions, ledger
 └─ Telemetry     ── per-stage latency, per-call credit estimate, request_ids
```

### Why this shape
- **Single Gnani gateway** because concurrency limits are unknown and may be one active request per account [A, 01 E2]. All Gnani traffic goes through one `asyncio` limiter with priorities: `live` > `preview` > `smoke`. LLM-only traffic bypasses it.
- **Push-to-talk turns on REST STT as the default input** [O]. Reason: REST is verified, simple, supports `prisma-v3.0` hints (`keyterms`, `topic`, `previous_text`, `indic-auto`), and a 30 s clip limit is fine for turns. Realtime WebSocket needs 1,024-byte paced frames, header-only config and a backend proxy; it also contends for the concurrency cap. Ship REST first; add WebSocket only if Phase 0 shows it works within limits and time remains.
- **TTS via SSE for playback** so the first audio chunk plays before synthesis ends, with REST as fallback. Sentence-level chunking: the LLM reply is split into sentences, each synthesised (cache by hash) and queued to the browser in order. Measure chunk format in Phase 0 (01 E5).
- **Browser audio**: MediaRecorder produces webm/opus; backend converts with `ffmpeg` to 16 kHz mono wav before upload (or send as `.ogg`/`.webm` only if the API accepts the extension; STT lists wav, mp3, ogg, flac, aac, m4a — webm is NOT listed, so convert).

### Compiler stages (a straight pipeline, not "agents")
1. **Capture**: audio → Prisma v3.0 (`indic-auto`, `format=codemix` or `transcribe`, probe v2.5 fallback) → transcript with detected language. The UI shows the transcript and lets the user correct it by text.
2. **Intent extraction**: LLM → `RequirementSet` JSON (schema in 03 appendix) with each item carrying `source: stated|inferred|defaulted` and `evidence` (transcript span or reason).
3. **Gap analysis**: deterministic rules + LLM identify missing high-impact info (languages, escalation target, hours, policy numbers, tone). At most **3 questions**, asked by voice (Timbre) with sensible defaults pre-filled; user may say "you decide", which marks fields `defaulted`. Never block on questions; unattended mode picks defaults.
4. **Capability negotiation**: pure code. Maps `RequirementSet` → platform capabilities. Chooses TTS model+voice+language policy, STT hints, session limits, `unsupported[]`. Rules in 03 appendix.
5. **Spec synthesis**: LLM → `AgentSpec` (persona, goals, tools/actions as stubs, policies, escalation, refusal rules, knowledge facts as an inline FAQ list with `facts[]`, opening line, closing line, language policy, voice config, voice-style guide). Then **voice-readiness lint** (deterministic) auto-fixes or flags.
6. **Test synthesis + simulation + repair**: LLM writes N test scenarios from the spec (each tied to a spec clause: policy, escalation, confidentiality, language switch, ambiguity, injection). Simulator runs them in text mode; judge scores `pass|fail` with a quoted evidence turn. Failures → repair patch to the spec (JSON Patch on `AgentSpec`), rerun failed + a sample of passes. Max 2 repair rounds. Output: `TestReport`.

Then **Deploy** (writes version row, runs smoke test: one real voice round trip using canned synthetic audio generated by Timbre; verifies STT transcript contains expected keyword; marks `live`).

### Runtime (the part that proves "it actually works")
Per session: `system = render(AgentSpec)`; loop: user audio → STT → (detected language, transcript) → LLM with history and spec-driven guardrails → reply → voice-lint → sentence split → TTS (voice/language chosen per sentence by language policy) → stream to browser. Tool/actions are **simulated against a synthetic in-memory store** declared in the spec (e.g. fake orders `ORD-1001..1010`) so a support agent can look up an order in the demo without real data. Escalation emits a `handoff` event shown in the UI. Transcript, per-turn latency (STT, LLM, TTS first byte) and estimated credits displayed live.

### Persistence
SQLite tables: `agents(id, name, created_at)`, `spec_versions(id, agent_id, version, spec_json, provenance_json, status)`, `test_runs(id, version_id, report_json, started_at)`, `sessions(id, agent_id, version_id, turns_json)`, `gnani_ledger(id, ts, kind, model, units, est_credits, request_id, status, latency_ms)`, `tts_cache(key, path, bytes)`.

### Failure handling (must be implemented, not described)
- 429/5xx/504 from Gnani → backoff per 01; after 3 failures the UI shows the failure and offers text input; TTS failure → show text with a "voice unavailable" badge; 402/403 → "credits exhausted or scope missing" banner + text mode. Nothing crashes the pipeline.
- LLM malformed JSON → one repair re-ask with the validation error; then fail the stage with a visible error.
- Every stage persists its output so a retry resumes rather than restarts.

### Security and privacy
Keys only in env on the backend, never logged, never in frontend bundle or prompts. Redact keys in logs. Synthetic data only; the UI shows a banner "Demo uses synthetic data only — don't speak real personal details". Per-session rate limit and a global daily credit guard (hard stop at 70% of the observed balance). Do not store raw user audio beyond the session (delete temp files after STT).

## 3. Alternatives considered

| Option | Why not |
|---|---|
| Call Inya Agent Builder Platform API to create real Gnani agents | Out of scope per FAQ; no participant key; would fail or breach rules (01 B) |
| Self-host Evon v3.3 as the brain | Gated weights, needs a GPU node; not feasible in under 7 hours; keep as documented future work |
| Multi-agent swarm inside Hatch | Adds latency/failure surface; a staged pipeline with a deterministic negotiator is smaller and more testable |
| Realtime WebSocket STT as default | Header-only config, strict 1,024-byte pacing, concurrency cap unknown; REST first |
| Telephony/phone calls | No participant-available telephony; skip |

## 4. Scope, in priority order (what must exist by the deadline)

**P0 (must work end to end):** Phase 0 probes; GnaniGateway; push-to-talk capture → transcript → RequirementSet → AgentSpec (with provenance) → capability negotiation → live runtime voice call in browser with Hindi/Hinglish/English; deploy page `/a/<id>`; ledger and latency displayed.
**P1 (the differentiators, build in this order):** voice-readiness lint; text-mode simulation with 6–8 scenarios and judge; one repair round; spec view with provenance badges; voice-asked clarifying questions (max 3).
**P2 (only if everything above is green):** voice edit with regression diff; Kannada/Tamil demo agent; WebSocket STT; `inya_export.json` (export-only, clearly labelled); share link/QR.
**Cut without regret:** accounts, auth beyond a demo token, analytics dashboards, voice cloning, telephony, RAG.

## 5. Time plan (today is 14 Nov, deadline 15 Nov 18:00 IST is the *final* cutoff; Copilot works while the user prepares the demo)
Because engagement on the nominated post is counted up to the closing cutoff and the post must exist before submitting, **target: working demo by 16:00 on 14 Nov (not 15 Nov)**, video posted by 17:00 on 14 Nov, submission form filed by 20:00 on 14 Nov, leaving 15 Nov as buffer for engagement and fixes. If the user is reading this on the 15th, compress: P0 only, post by noon.

Phases for Copilot (state each in `PROGRESS.md` with timestamps):
- Phase 0 (≤30 min): scaffolding, env, Gnani probes, write `docs/VERIFIED_GNANI.md` and credit/latency numbers.
- Phase 1 (≤90 min): Gateway + STT + TTS + minimal runtime echo agent over HTTP/WS; browser mic round trip works.
- Phase 2 (≤90 min): compiler stages 1–5, spec store, UI for create/inspect.
- Phase 3 (≤60 min): simulator + judge + repair + lint; test report UI.
- Phase 4 (≤45 min): polish, failure paths, README, demo script rehearsal, smoke test, run all tests.
Anything unfinished is cut to the next priority tier, not rushed.
