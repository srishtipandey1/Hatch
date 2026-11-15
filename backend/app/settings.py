from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


load_env()

GNANI_API_KEY = os.getenv("GNANI_API_KEY", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "openai/gpt-oss-20b")
GNANI_MAX_CONCURRENCY = max(1, int(os.getenv("GNANI_MAX_CONCURRENCY", "1")))
CREDIT_BUDGET_INR = float(os.getenv("CREDIT_BUDGET_INR", "3000"))
# Conservative planning estimates used when the dashboard delta cannot be measured.
# They are deliberately above the only public figure (about INR 27 per audio hour of
# Prisma v2.5) so the ledger overstates rather than understates spend. Override with
# measured values in .env as soon as they are available.
STT_COST_INR_PER_SECOND = float(os.getenv("STT_COST_INR_PER_SECOND") or "0.05")
TTS_COST_INR_PER_1000_CHARS = float(os.getenv("TTS_COST_INR_PER_1000_CHARS") or "0.50")
PRISMA_MODEL = os.getenv("PRISMA_MODEL", "prisma-v3.0")
TIMBRE_MODEL = os.getenv("TIMBRE_MODEL", "timbre-v3.0")
TTS_VOICE = os.getenv("TTS_VOICE", "Shivani")
DATA_DIR = ROOT / "data"
AUDIO_CACHE_DIR = ROOT / "audio_cache"
