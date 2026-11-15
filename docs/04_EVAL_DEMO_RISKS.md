# 04 — Evaluation, Demo, Risks, Review Loop

## 1. Evaluation strategy (all implementable; no invented scores)

Measure Hatch, not just HTTP success. Four layers; layers 1–3 are automatic and cost no Gnani credits.

**Layer 1 — Spec quality (deterministic + LLM judge)**
Golden requests (store as `eval/golden/*.json`, each with the request text and a checklist of expected spec properties):
1. Hindi appointment-booking agent (clinic; collect name, preferred slot; escalate emergencies).
2. Hinglish kirana order-taking agent (items, quantities, delivery slot; confirm order back).
3. English customer-support agent (orders, returns; polite with angry callers; escalate complex cases).
4. Multilingual restaurant reservation (Hindi, English, Tamil; party size, time).
5. Kannada information assistant (bus timings from the FAQ; refuses other topics).
6. Escalation-heavy agent (must hand off in defined situations).
7. Confidentiality agent (must never reveal an internal discount code in the FAQ).
8. Complex multi-responsibility agent (support + booking + feedback).
9. Under-specified request ("make me a helpful agent for my shop") — must trigger ≤3 questions and visible `defaulted` fields, not invention.
10. Unsupported request ("also call my customers on their phone in Assamese") — must produce `unsupported[]` with alternatives.
Checks per case: JSON validates; every field has provenance; languages within supported set; voice/model pair valid per doc 01 catalog; lint clean; each stated requirement appears in the spec (LLM judge with quoted evidence); no hallucinated facts (every `knowledge` fact traces to the transcript, otherwise flagged `inferred`/`defaulted`).

**Layer 2 — Behavioural conformance (simulated callers, text mode)**
For each golden agent run 8–12 scenarios (personas in doc 03 §6). Report per case: scenario pass rate, which clauses failed, and whether one repair round improved it. Record *before repair* and *after repair*; the delta is the feature's measured value. Report raw counts (e.g. "9/12 → 11/12"), never a made-up percentage.
Also run the **injection and confidentiality** scenarios against every agent; any leak is a hard failure.
Judge reliability: spot-check 20 verdicts by hand and record agreement; report it honestly with the sample size.

**Layer 3 — Regression**
Voice-edit test: apply three edits (tone, add a policy, change language) to a golden agent; confirm previously passing scenarios still pass or are explicitly reported as changed.

**Layer 4 — Real voice path (credit-limited, run a handful of times)**
`make smoke` plus a manual protocol of 10 spoken utterances (3 Hindi, 3 Hinglish, 2 English, 1 Kannada, 1 Tamil — spoken by the user, synthetic content only): record transcript correctness (human judged), STT latency, LLM latency, TTS first-byte latency, end-to-end turn latency, credits consumed. Report a table of measured numbers with n. Compare `prisma-v3.0` vs `prisma-v2.5` on the same clips only if credits allow; say if you didn't.

**Operational metrics to log every run:** stage latencies, number of Gnani calls, number of LLM calls and tokens, estimated credits, failures by type.

## 2. Demo strategy (60–90 s video; one take, no cuts that hide failures)

Goal of the first 10 seconds: a viewer understands "I spoke, and a working voice agent exists".
Script (Hinglish request, deliberately a bit vague):
1. (0–10 s) Press mic, say in Hinglish: "Mere kapde ki dukaan ke liye ek customer support agent banao — orders, return policy, aur gusse wale customers ko politely handle karna, aur mushkil cases human ko dena." On screen: live transcript with detected language.
2. (10–30 s) Compile view: spec fills with provenance badges; two defaulted fields highlighted; one spoken clarifying question answered by voice ("tum decide karo"); one `unsupported` item shown honestly.
3. (30–50 s) Test report: 10 simulated callers, 8 pass, 2 fail → repair → rerun → show the patch diff and the improved count (use whatever the real run produces).
4. (50–80 s) Open `/a/<id>`, hold a real voice conversation with the created agent: ask about a fake order `ORD-1004`, get angry ("mera order late hai!"), and trigger a handoff to a human. Latency/credit panel visible.
5. (80–90 s) One voice edit: "ise aur polite banao aur exchange bhi handle karo" → diff → regression check passes.
End card text: "Hatch — say it, hatch it, talk to it." plus models used (Prisma, Timbre) and "runs on the Hatch runtime; built for #GreatIndianAIInternshipChallenge".
Fit award categories honestly where true (code-mixed, Demo-Day 60-second video, solo or duo); do not claim ones not earned.
Post: LinkedIn and/or X with `#GnaniAI #GreatIndianAIInternshipChallenge`, tag Gnani's official account, state the models used, include the repo link. Nominate the post link in the submission form. Ask real friends to look; no engagement buying or swaps (rule 5).
Record a backup video in case the live call is flaky; label it as a recording if used.

## 3. Risks, dependencies, limitations (honest)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Programme key lacks `prisma-v3.0`/`timbre-v3.0` (403 `SCOPE_NOT_ALLOWED`) | Medium | Medium | Phase 0 probe; v2.5 path is fully specified |
| R2 | Concurrency limit of 1 active request stalls the live turn loop | Medium | High | Single gateway queue; sequential STT→LLM→TTS; sentence-level TTS cache; measure in Phase 0 |
| R3 | 5,000 credits run out during testing | Medium | High | Text-mode tests; cache; 70% guard; measure cost in Phase 0; ask Gnani on Discord |
| R4 | Doc/API mismatches (header names, chunk format, text-length limits) | High | Medium | Phase 0 probes; `DECISIONS.md` |
| R5 | No LLM key chosen / provider latency high | Medium | High | User must supply `LLM_*` env today; choose a fast model; streaming optional |
| R6 | Third-party LLM may weigh against "genuine Gnani use" | Low–Medium | Medium | Gnani Prisma/Timbre are core to input and output; disclose; ask on Discord (question 4 in doc 01) |
| R7 | Indic STT errors on noisy mic / Hindi–Marathi ambiguity | Medium | Medium | Visible transcript with edit; `keyterms`; explicit language hints |
| R8 | Simulated-caller judge is itself an LLM and can be wrong | Medium | Medium | Quote evidence; spot-check agreement; hard-fail only on leaks |
| R9 | Browser audio formats (webm) not accepted by STT | High if unhandled | High | ffmpeg conversion to wav |
| R10 | Time: <7 h to deadline | High | High | Phase caps; cut order P2→P1; P0 end-to-end first |
| R11 | Eligibility/terms (enrolled student, age, team of ≤2) are the user's responsibility | — | Critical | User confirms eligibility; this work does not substitute for it |
| R12 | Engagement-based shortlisting is outside engineering control | — | — | Post early; be authentic |

Honest limitations to state in the README/submission: agents run on our runtime, not on Gnani Agent Builder; no telephony; actions run against synthetic data; a third-party LLM is used for reasoning; judge scores are LLM-produced; quality numbers are from small samples.

## 4. Gnani support questions (post in the official Discord; text in doc 01 §B)

## 5. How Copilot's results come back to me for independent review

Use the **Review Bundle** so I can audit without reading the whole repo. Copilot writes it to `review/phase_N/` and you paste or upload the contents here.

Contents per phase:
1. `STATUS.md`: feature list with `DONE (verified by: <cmd>)`, `PARTIAL`, `NOT DONE`.
2. `git log --oneline -30` and `git diff --stat` since last phase.
3. Output of `make test` (last 60 lines) and `make smoke` (full, secrets redacted).
4. `docs/VERIFIED_GNANI.md` (Phase 0) and any new `DECISIONS.md` entries.
5. For Phase 2–3: three real compiled specs (JSON) + the `TestReport` for one golden request + the telemetry table (latencies, calls, estimated credits).
6. Errors: exact stack traces or HTTP bodies (redact keys), with the command that produced them.
7. Screenshots (create screen, spec view, test report, live call) and the demo video draft.

Rules for what you bring back: paste raw outputs, not summaries; include the failing command; never paste API keys. I will check claims against the evidence, flag anything Copilot reported as done without proof, and send back prioritised fixes.

## 6. Final checklist before submission (user-owned)
- [ ] Eligibility confirmed (enrolled in India, 18+, solo or team of ≤2).
- [ ] Registered; programme credits visible in `app.gnani.ai/voice`.
- [ ] Demo uses only synthetic data; no real phone numbers/IDs/recordings.
- [ ] Video posted on LinkedIn/X with both hashtags and Gnani tagged; link works.
- [ ] Submission form filled: project name, problem, users, Gnani models/APIs (Prisma, Timbre; say which versions actually used), individual contributions, video, written explanation, post link(s).
- [ ] Repo link and README truthful (runtime is ours; LLM is third-party).
- [ ] Submitted before 15 Nov 2026 18:00 IST.
