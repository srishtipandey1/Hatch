from __future__ import annotations

import asyncio
import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg


class AudioConversionError(Exception):
    pass


def _convert_web_audio(audio: bytes, suffix: str) -> bytes:
    try:
        executable = imageio_ffmpeg.get_ffmpeg_exe()
    except (FileNotFoundError, RuntimeError) as error:
        raise AudioConversionError(
            "FFmpeg is unavailable; voice input cannot be converted. Type your message instead."
        ) from error
    with tempfile.TemporaryDirectory(prefix="hatch-audio-") as directory:
        source = Path(directory) / f"input{suffix}"
        target = Path(directory) / "turn.wav"
        source.write_bytes(audio)
        try:
            subprocess.run(
                [
                    executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(source), "-t", "31", "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(target),
                ],
                check=True,
                capture_output=True,
                timeout=45,
            )
        except subprocess.TimeoutExpired as error:
            raise AudioConversionError("Audio conversion timed out. Try a shorter recording.") from error
        except subprocess.CalledProcessError as error:
            raise AudioConversionError("Could not decode this recording. Try recording again.") from error
        except FileNotFoundError as error:
            raise AudioConversionError(
                "FFmpeg is unavailable; voice input cannot be converted. Type your message instead."
            ) from error
        if not target.is_file():
            raise AudioConversionError("Audio conversion did not produce a WAV file.")
        try:
            with wave.open(str(target), "rb") as wav_file:
                duration = wav_file.getnframes() / wav_file.getframerate()
        except (wave.Error, OSError, ZeroDivisionError) as error:
            raise AudioConversionError("Converted audio was invalid. Try recording again.") from error
        if duration > 30:
            raise AudioConversionError("Recordings must be 30 seconds or shorter.")
        return target.read_bytes()


async def to_wav(audio: bytes, filename: str) -> bytes:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".mp4"}:
        suffix = ".webm"
    return await asyncio.to_thread(_convert_web_audio, audio, suffix)
