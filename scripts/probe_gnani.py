from __future__ import annotations

import json
import os
import re
import sys
import time
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.vachana.ai"


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


def safe_body(response: httpx.Response, secrets: list[str]) -> str:
    text = response.text[:600]
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(x-api-key-id|authorization)(\s*[=:]\s*)[^,}\s]+", r"\1\2[REDACTED]", text)
    return text


def redact(value: object, secrets: list[str]) -> object:
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    return value


def summarize(response: httpx.Response, started: float, secrets: list[str]) -> dict[str, object]:
    result: dict[str, object] = {
        "http_status": response.status_code,
        "wall_seconds": round(time.perf_counter() - started, 3),
    }
    request_id = response.headers.get("X-API-Request-ID") or response.headers.get("X-Request-ID")
    if request_id:
        result["response_request_id"] = request_id
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        for field in ("success", "request_id", "model", "transcript", "detected_language_code",
                      "processing_time", "end_to_end_latency", "message", "error", "detail"):
            if field in payload:
                value = redact(payload[field], secrets)
                result[field] = value if field != "transcript" else str(value)[:120]
    elif response.is_error:
        result["body"] = safe_body(response, secrets)
    else:
        result["content_type"] = response.headers.get("content-type", "unknown")
        result["audio_bytes"] = len(response.content)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Make one v3.0 TTS request and one STT request.")
    args = parser.parse_args()
    load_env()
    gnani_key = os.getenv("GNANI_API_KEY", "")
    llm_key = os.getenv("LLM_API_KEY", "")
    llm_base = os.getenv("LLM_BASE_URL", "").rstrip("/")
    llm_model = os.getenv("LLM_MODEL", "")
    missing = [name for name, value in (
        ("GNANI_API_KEY", gnani_key), ("LLM_API_KEY", llm_key),
        ("LLM_BASE_URL", llm_base), ("LLM_MODEL", llm_model),
    ) if not value]
    if missing:
        print("Missing required environment variables: " + ", ".join(missing))
        return 2

    secrets = [gnani_key, llm_key]
    headers = {"X-API-Key-ID": gnani_key}
    report: dict[str, object] = {
        "timestamp_ist": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
        "safety_scope": "Serial authenticated checks only; no concurrency, rate-limit, or invalid-key tests.",
        "gnani": {},
        "llm": {},
    }
    audio_samples: dict[str, bytes] = {}
    with httpx.Client(timeout=httpx.Timeout(35.0), follow_redirects=False) as client:
        tts_checks = (("timbre-v3.0", "Shivani"),) if args.smoke else (
            ("timbre-v2.5", "Nalini"), ("timbre-v3.0", "Shivani")
        )
        for model, voice in tts_checks:
            name = f"tts_{model}"
            started = time.perf_counter()
            try:
                response = client.post(
                    f"{API}/api/v1/tts/inference",
                    headers=headers,
                    json={
                        "text": "Namaste, aapki sahayata ke liye main yahan hoon.",
                        "model": model,
                        "voice": voice,
                        "language": "hi-IN",
                        "audio_config": {
                            "sample_rate": 16000,
                            "num_channels": 1,
                            "sample_width": 2,
                            "encoding": "pcm_s16le",
                            "container": "wav",
                        },
                    },
                )
                report["gnani"][name] = summarize(response, started, secrets)
                if response.is_success and response.content:
                    audio_samples[model] = response.content
            except httpx.HTTPError as error:
                report["gnani"][name] = {"error_type": type(error).__name__}

        stt_checks = list(audio_samples.items())
        if args.smoke:
            stt_checks = stt_checks[:1]
        for model, audio in stt_checks:
            stt_model = "prisma-v3.0" if model == "timbre-v3.0" else "prisma-v2.5"
            data = {
                "language_code": "indic-auto" if stt_model == "prisma-v3.0" else "hi-IN",
                "format": "codemix" if stt_model == "prisma-v3.0" else "transcribe",
            }
            if stt_model == "prisma-v3.0":
                data["model"] = stt_model
            started = time.perf_counter()
            try:
                response = client.post(
                    f"{API}/stt/v3",
                    headers=headers,
                    data=data,
                    files={"audio_file": (f"{model}.wav", audio, "audio/wav")},
                )
                report["gnani"][f"stt_{stt_model}"] = summarize(response, started, secrets)
            except httpx.HTTPError as error:
                report["gnani"][f"stt_{stt_model}"] = {
                    "error_type": type(error).__name__
                }

        if not args.smoke:
            started = time.perf_counter()
            try:
                response = client.post(
                    f"{llm_base}/chat/completions",
                    headers={"Authorization": f"Bearer {llm_key}"},
                    json={
                        "model": llm_model,
                        "messages": [{"role": "user", "content": "Reply with the single word OK."}],
                        "max_tokens": 8,
                    },
                )
                result: dict[str, object] = {
                    "http_status": response.status_code,
                    "wall_seconds": round(time.perf_counter() - started, 3),
                }
                if response.is_success:
                    payload = response.json()
                    result["success"] = bool(payload.get("choices"))
                    result["model"] = payload.get("model", "not returned")
                else:
                    result["body"] = safe_body(response, secrets)
                report["llm"] = result
            except httpx.HTTPError as error:
                report["llm"] = {"error_type": type(error).__name__}

    if args.smoke:
        print(json.dumps({"gnani": report["gnani"]}, indent=2, ensure_ascii=True))
        return int(not report["gnani"] or any(
            not isinstance(result, dict) or result.get("http_status") != 200
            for result in report["gnani"].values()
        ))

    out = ROOT / "docs" / "VERIFIED_GNANI.md"
    gnani_lines = ["# Gnani and LLM probe results", "", f"Probe timestamp: {report['timestamp_ist']}", "",
                   "Checks were serial and limited to one request per eligible model. This probe did not issue concurrent traffic, intentionally exceed a rate limit, or send an invalid credential.",
                   "", "## Results", ""]
    for name, result in report["gnani"].items():
        gnani_lines.extend([f"### `{name}`", "", "```json", json.dumps(result, indent=2, ensure_ascii=False), "```", ""])
    gnani_lines.extend(["## LLM connectivity", "", "```json",
                        json.dumps(report["llm"], indent=2, ensure_ascii=False), "```", "",
                        "## Not measured", "",
                        "- Request concurrency and rate-limit thresholds; do not infer them from this serial probe.",
                        "- Dashboard credit cost, because before/after balances were not available.",
                        "- SSE chunk framing, maximum accepted text length, and realtime WebSocket header variants.",
                        "- Error response shapes requiring invalid credentials or deliberate fault injection.",
                        "", "## Decisions this implies", "",
                        "- API/model defaults remain provisional until successful results above confirm account access.",
                        "- Keep Gnani calls serial at concurrency one.",
                        "- Do not estimate unit prices without dashboard measurements.",
                        "- Use REST push-to-talk; defer realtime WebSocket probing.",
                        ""])
    out.write_text("\n".join(gnani_lines), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}; credentials and LLM response text were not recorded.")
    print(json.dumps({"gnani": report["gnani"], "llm": report["llm"]}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
