# Hatch

Build voice agents in seconds.

Hatch turns a spoken or typed description into a working voice agent. Describe what you need in Hindi, Hinglish, or English — Hatch compiles a spec, tests it with simulated callers, repairs what breaks, and gives you a live agent you can talk to immediately.

Built for the Gnani Great Indian AI Internship Challenge. Uses Gnani Prisma (STT) and Timbre (TTS).

## Features

- **Voice-first input** — Describe your agent by speaking or typing
- **Automatic spec generation** — Extracts requirements, responsibilities, escalation policies, and conversation flows
- **Simulated testing** — Runs your agent against 7 realistic caller scenarios before you talk to it
- **Self-repair loop** — Automatically fixes issues found during testing
- **Multilingual** — Hindi, Hinglish, English, and 8+ Indic languages via Gnani Prisma
- **Live conversation** — Talk to your agent with real-time voice or text
- **Cost tracking** — Real-time ledger showing Gnani API usage and estimated costs

## Quick Start

### Requirements

- Python 3.11+
- Node.js LTS (v20+)
- Gnani API key (get yours at app.gnani.ai)
- Groq API key (for LLM reasoning)

### Setup

```powershell
# Clone and install
git clone <your-repo-url>
cd hatch
python -m pip install -r requirements.txt

# Install frontend
cd frontend
npm install
cd ..

# Configure environment
Copy-Item .env.example .env
# Edit .env with your API keys:
# - GNANI_API_KEY
# - GNANI_BASE_URL (default: https://api.vachana.ai)
# - LLM_BASE_URL (default: https://api.groq.com/openai/v1)
# - LLM_MODEL (default: llama-3.1-70b-versatile)
# - LLM_API_KEY

# Run both backend and frontend
python scripts/dev.py
```

Open http://localhost:5173 to start building agents.

API documentation is available at http://localhost:8000/docs.

## How It Works

### The Four Steps

1. **Speak or Type** — Describe your agent in natural language
   Example: "Mere kapde ki dukaan ke liye ek customer support agent banao. Orders aur return policy handle karo."

2. **Compile** — Hatch extracts requirements, writes the spec, and lints for voice-readiness

3. **Test** — Seven simulated callers stress-test your agent; failures trigger automatic repairs

4. **Talk** — Have a real conversation with your agent via voice or text

### Architecture

Hatch runs its own agent runtime — it does not use Gnani Agent Builder. This gives full control over agent behavior, testing, and iteration.

```
User (voice/text) → Hatch Compiler + Runtime → Gnani Prisma + Timbre
                                      ↓
                                 Groq LLM (reasoning)
```

## Testing

### Unit Tests (no API credits)

```powershell
python scripts/test.py
```

Tests use fakes and do not spend Gnani credits.

### Smoke Check (spends minimal credits)

```powershell
# Start the app first
python scripts/dev.py

# In another terminal
python scripts/smoke.py
```

The smoke check performs one synthetic TTS to STT round trip (approximately ₹0.01).

## Models and APIs

| Component | Model/API | Provider |
|-----------|-----------|----------|
| Speech-to-Text | Prisma v2.5/v3.0 | Gnani |
| Text-to-Speech | Timbre v2.5/v3.0 | Gnani |
| Reasoning | Llama 3.1 70B | Groq |
| Voice Cloning | Not used (out of scope) | — |

**Note:** Hatch uses synthetic data only. Do not speak or enter real personal, financial, or account details.

## Supported Languages

Hindi, English, Bengali, Gujarati, Kannada, Malayalam, Marathi, Punjabi, Tamil, Telugu

## Project Structure

```
hatch/
├── backend/           # Python FastAPI server
│   ├── agents/        # Agent compilation and runtime
│   ├── voice/         # Gnani STT/TTS integration
│   ├── llm/           # LLM reasoning layer
│   └── test/          # Simulated caller scenarios
├── frontend/          # React + Vite + TypeScript
│   └── src/
│       ├── main.tsx   # Main app component
│       └── style.css  # Styles
├── scripts/
│   ├── dev.py         # Run both backend and frontend
│   ├── test.py        # Run test suite
│   └── smoke.py       # Smoke check script
├── docs/              # Technical documentation
└── README.md
```

## Privacy and Safety

- **Synthetic data only** — This is a demo. Never use real customer data, phone numbers, account details, or recorded calls.
- **API keys stay on backend** — Keys are loaded from `.env` and never committed to version control.
- **No persistent recordings** — Voice clips are processed in real-time and discarded.

## Limitations

- **Demo scope** — Supports synthetic order lookup (ORD-1001 to ORD-1010) and return policy queries only
- **No telephony** — Voice interaction is browser-based; no phone integration
- **No real actions** — Agent cannot place orders, process refunds, or access external systems
- **Estimates only** — Test results and cost projections are small-sample estimates, not guarantees

## License

MIT License — see LICENSE for details.

---

Built for the Gnani Great Indian AI Internship Challenge

Deadline: 15 Nov 2026, 18:00 IST
