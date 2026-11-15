# Gnani and LLM probe results

Probe timestamp: 2026-11-15T11:52:02+05:30

Checks were serial and limited to one request per eligible model. This probe did not issue concurrent traffic, intentionally exceed a rate limit, or send an invalid credential.

## Results

### `tts_timbre-v2.5`

```json
{
  "http_status": 200,
  "wall_seconds": 0.806,
  "response_request_id": "01a1ddde-b432-7852-8aa3-b705da534e43",
  "content_type": "audio/wav",
  "audio_bytes": 97324
}
```

### `tts_timbre-v3.0`

```json
{
  "http_status": 200,
  "wall_seconds": 3.778,
  "response_request_id": "01a1ddde-b722-7a42-9898-cd87fadb6d35",
  "content_type": "audio/wav",
  "audio_bytes": 107564
}
```

### `stt_prisma-v2.5`

```json
{
  "http_status": 200,
  "wall_seconds": 0.191,
  "success": true,
  "request_id": "01a1ddde-c5fb-75e4-8643-b98d6d3485ce",
  "model": "prisma-v2.5",
  "transcript": "नमस्ते, आपकी सहायता के लिए मैं यहाँ हूँ।",
  "processing_time": 0.08475112915039062,
  "end_to_end_latency": 0.09559392929077148
}
```

### `stt_prisma-v3.0`

```json
{
  "http_status": 200,
  "wall_seconds": 0.205,
  "success": true,
  "request_id": "01a1ddde-c6a7-7029-ad94-6eeaee2a1f05",
  "model": "prisma-v3.0",
  "transcript": "नमस्ते, आपकी सहायता के लिए मैं यहाँ हूँ।",
  "detected_language_code": "hi-IN",
  "processing_time": 0.11170578002929688,
  "end_to_end_latency": 0.11355924606323242
}
```

## LLM connectivity

```json
{
  "http_status": 200,
  "wall_seconds": 0.463,
  "success": true,
  "model": "openai/gpt-oss-120b"
}
```

## Not measured

- Request concurrency and rate-limit thresholds; do not infer them from this serial probe.
- Dashboard credit cost, because before/after balances were not available.
- SSE chunk framing, maximum accepted text length, and realtime WebSocket header variants.
- Error response shapes requiring invalid credentials or deliberate fault injection.

## Additional contract correction

- The documented Timbre API accepts symbolic speed values such as `medium`, but a real v3.0 request with `speed="medium"` returned HTTP 400: `Input should be a valid number, unable to parse string as a number at body -> speed`. Omitting `speed` succeeds. Hatch sends numeric `1.0` (the provider's default-rate value) instead.

## Decisions this implies

- API/model defaults remain provisional until successful results above confirm account access.
- Keep Gnani calls serial at concurrency one.
- Do not estimate unit prices without dashboard measurements.
- Use REST push-to-talk; defer realtime WebSocket probing.
- Send numeric TTS `speed` (`1.0` default); the documented symbolic value was rejected.
