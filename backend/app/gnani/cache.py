from __future__ import annotations

import hashlib
import json
from pathlib import Path


class TTSCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*, model: str, voice: str, language: str, speed: float, text: str) -> str:
        canonical = json.dumps(
            [model, voice, language, speed, text], ensure_ascii=False, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> bytes | None:
        path = self.directory / f"{key}.wav"
        return path.read_bytes() if path.is_file() else None

    def put(self, key: str, audio: bytes) -> None:
        target = self.directory / f"{key}.wav"
        temporary = self.directory / f".{key}.tmp"
        temporary.write_bytes(audio)
        temporary.replace(target)
