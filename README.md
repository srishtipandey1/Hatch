# Hatch

**Say it. Hatch it. Talk to it.**

Hatch turns a spoken or typed description into a provenance-tracked voice-agent specification, tests it with simulated callers, and serves the agent on the Hatch runtime using Gnani Prisma (speech in) and Timbre (speech out).

## Requirements

- Python 3.11+
- Node.js LTS
- `.env` populated with the variables in `.env.example`

The backend uses the bundled ffmpeg binary from `imageio-ffmpeg`; a separate system installation is not required.

## Run

```powershell
python -m pip install -r requirements.txt
Push-Location frontend
npm install
Pop-Location
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Fill in .env locally; never commit it.
python scripts/dev.py
```

Open the URL that Vite prints (normally <http://localhost:5173>). Backend API docs are at <http://localhost:8000/docs>.

## Tests and smoke check

```powershell
python scripts/test.py
# Start the app first; speech requires GNANI_API_KEY.
python scripts/smoke.py
```

Automated tests use fakes and do not spend Gnani credits. The smoke check uses the local gateway for one synthetic TTS-to-STT round trip and therefore spends a small, ledgered amount.

## Models and limitations

Speech uses the Gnani Prisma STT and Timbre TTS APIs. Reasoning uses the third-party OpenAI-compatible LLM configured by `LLM_BASE_URL` / `LLM_MODEL`; Evon is not available as a hosted API. Agents run on the Hatch runtime, not Gnani Agent Builder. Calls and action data are synthetic; no telephony or real customer integrations are provided. LLM-generated evaluation results are small-sample estimates, not guarantees. Speech costs are conservative planning estimates because per-unit dashboard rates were not supplied; see [docs/CREDITS.md](./docs/CREDITS.md). Text compilation and simulation work even if speech is blocked by the local budget guard.

## Privacy

The demo uses synthetic data only. Do not speak or enter real personal, financial, or account details. API keys stay on the backend and must never be committed.

## How this was built

TODO: Repository owner to fill in.
