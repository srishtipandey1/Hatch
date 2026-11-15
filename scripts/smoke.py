from __future__ import annotations

import json
import sys

import httpx

API = "http://127.0.0.1:8000"


def _failure(response: httpx.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return {
        "http_status": response.status_code,
        "detail": payload.get("detail", "Request failed.") if isinstance(payload, dict) else "Request failed.",
    }


def main() -> int:
    try:
        with httpx.Client(timeout=45.0) as client:
            health = client.get(f"{API}/api/health")
            health.raise_for_status()
            tts = client.post(
                f"{API}/api/tts",
                json={
                    "text": "Namaste, aapki sahayata ke liye main yahan hoon.",
                    "language": "hi-IN",
                },
            )
            if tts.is_error:
                print(json.dumps({"tts": _failure(tts)}, indent=2))
                return 1
            voice = client.post(
                f"{API}/api/voice/turn",
                files={"audio": ("smoke.wav", tts.content, "audio/wav")},
            )
            if voice.is_error:
                print(json.dumps({"voice_turn": _failure(voice)}, indent=2))
                return 1
            result = voice.json()
            print(json.dumps({
                "tts_http_status": tts.status_code,
                "stt_model": result.get("stt_model"),
                "transcript_length": len(str(result.get("transcript", ""))),
                "round_trip_seconds": result.get("total_latency_seconds"),
                "ledger": result.get("ledger"),
            }, indent=2))
            return 0
    except httpx.HTTPError as error:
        print(f"Smoke check could not reach Hatch API ({type(error).__name__}). Start it with `python scripts/dev.py`.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
