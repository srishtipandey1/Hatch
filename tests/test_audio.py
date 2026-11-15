from __future__ import annotations

import asyncio
import io
import subprocess
import wave

import imageio_ffmpeg
import pytest

from backend.app.audio import AudioConversionError, to_wav


def _silent_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\0\0" * 1600)
    return output.getvalue()


def test_webm_recording_converts_to_mono_16khz_wav() -> None:
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    source = _silent_wav()
    webm = subprocess.run(
        [
            executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "wav",
            "-i", "pipe:0", "-c:a", "libopus", "-f", "webm", "pipe:1",
        ],
        input=source,
        check=True,
        capture_output=True,
        timeout=20,
    ).stdout

    converted = asyncio.run(to_wav(webm, "recording.webm"))
    with wave.open(io.BytesIO(converted), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() > 0


def test_missing_ffmpeg_returns_text_fallback_error(monkeypatch) -> None:
    def missing_ffmpeg() -> str:
        raise FileNotFoundError("missing executable")

    monkeypatch.setattr("backend.app.audio.imageio_ffmpeg.get_ffmpeg_exe", missing_ffmpeg)

    with pytest.raises(AudioConversionError, match="Type your message instead"):
        asyncio.run(to_wav(b"audio", "recording.webm"))
