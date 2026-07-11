---
name: voice-modalities
description: Wire an application onto stimulir's voice lane — one realtime WebSocket that covers speech-to-speech, live transcription, and text-to-speech in a single session. Use when a user wants to add voice to an app on stimulir, run a live voice session, transcribe speech, synthesize speech, or figure out which model/endpoint serves audio.
---

# Voice Modalities

One lane, three modalities. Stimulir's voice architecture is omni-model
native: the realtime WebSocket session speaks, listens, and transcribes —
the same way a vision-language model subsumes a separate OCR-then-LLM
pipeline. There are no separate STT/TTS engines to integrate. Everything
below was verified against the live gateway.

## The lane

| Capability | How the realtime session provides it | Status (verified) |
|---|---|---|
| Speech-to-speech | audio in (`send_audio` + `commit`) → spoken audio out (`AudioDelta`) | **Working** |
| Live transcription | the gateway injects input transcription — user speech arrives as `InputTranscript` events | **Working** |
| Text-to-speech | text in (`send_context` + `create_response`) → spoken audio out; verbatim under a TTS instruction | **Working** — verified character-exact |

Endpoint: `WS /api/v1/inference/realtime`. Auth: the workspace `hyb_*` key
(`Authorization: Bearer`, or `?api_key=` for clients that cannot set
headers). Metering: per-session minutes as `modality: "voice_realtime"`.

**Batch audio** (transcribe a stored file, bulk synthesis) is the chat
lane's job, not a separate engine: audio input parts on
`POST /api/v1/inference/chat/completions` — the audio twin of the vision
parts that already work. Not served yet (the upstream rejects audio parts
today); when it ships, a stored recording becomes one POST. Legacy
OpenAI-compat audio REST endpoints exist on the gateway but are not the
stimulir path — do not build against them.

## Placement rationale

Assumes `connect` has already run (CLI installed, authenticated, workspace
selected) so a `hyb_*` key exists. The helper uses the Python SDK's
realtime extra (`stimulir[realtime]`) rather than hand-rolling the
WebSocket protocol — the SDK owns the event schema, auth handshake, and
the once-only setup invariant.

## Preflight

```bash
python3 --version                      # 3.10+
uv sync                                # installs stimulir[realtime]
test -n "$STIMULIR_API_KEY" || grep -q api_key ~/.stimulir/credentials.json
```

## Providers and models

**Provider selection** via `?provider=` — this decides everything:

- `gemini` / `vertex` / `openai` — requires an **active BYOK credential for
  that provider** on the workspace (see `byok-register`). Vertex accepts a
  service-account JSON or an Express-Mode API key. Default models:
  `gemini-2.5-flash-native-audio-preview-12-2025` (gemini),
  `gemini-live-2.5-flash-preview-native-audio-09-2025` (vertex),
  `gpt-realtime` (openai). Override with `?model=`.
- `hybrie` — **no BYOK needed**; bridges to the in-cluster HybrIE omni
  engine (Qwen2.5-Omni). Availability depends on the deployment running
  the omni engine.

**Audio format**: 16 kHz mono PCM16 in; the SDK exposes
`INPUT_AUDIO_SAMPLE_RATE` / `OUTPUT_AUDIO_SAMPLE_RATE` constants — read
them rather than hardcoding.

## SDK usage

The pattern `realtime_smoke.py` wraps:

```python
from stimulir.realtime import (
    RealtimeClient, AudioDelta, TextDelta, InputTranscript, ResponseDone,
)

client = RealtimeClient(
    realtime_url="wss://api.stimulir.com/api/v1/inference/realtime?provider=vertex",
    api_key=None,                # falls back to STIMULIR_API_KEY / ~/.stimulir
    instructions="You are a concise voice assistant.",
    # modalities defaults to audio — see anti-patterns before overriding
)
async with client.connect() as conn:
    await conn.setup()           # exactly once per connection
    await conn.send_audio(pcm16_chunk)   # or conn.send_context("text")
    await conn.commit()
    async for event in conn.events():
        if isinstance(event, AudioDelta):
            play(event.pcm16)
        elif isinstance(event, InputTranscript):
            log(event.text)      # live transcription, gateway-injected
        elif isinstance(event, ResponseDone):
            break
```

Smoke it bounded (never leave the socket open past the check):

```bash
python helpers/realtime_smoke.py --provider vertex --say "Say exactly: VOICE LANE OK"
```

**Text-to-speech** through the same session — pin the model to verbatim
delivery and write the spoken response to a WAV you name:

```bash
python helpers/realtime_smoke.py --provider vertex \
  --instructions "You are a text-to-speech engine. Speak the user's text exactly as written, nothing else." \
  --say "Text you want spoken." \
  --out-wav speech.wav
```

Verified: character-exact speech, playable 24 kHz WAV. It is an LLM
speaking under instruction — verbatim in practice, probabilistic in
principle; for interactive apps already holding a session this is simply
the lane's normal output.

**Speech-to-text** of a short clip through the same session — send the
audio, read the injected transcription:

```bash
python helpers/realtime_smoke.py --provider vertex --wav clip.wav
# summary.input_transcripts carries the transcription
```

**Close codes** when the connection drops instead of erroring in-band:
`4400` bad request, `4401` unauthorized, `4403` forbidden (missing BYOK for
the chosen provider), `4410` upstream provider rejected the session — check
the model id and modalities first, it is usually one of those.

## Anti-patterns (do NOT do)

- **Building against the legacy audio REST endpoints.** The gateway's
  OpenAI-compat `/audio/speech` and `/audio/transcriptions` routes are not
  the stimulir path — voice is the realtime lane now, batch audio is the
  chat lane's audio parts when they ship. (They also have no `/v1` alias
  and currently return errors.)
- **Forcing `modalities=["text"]` on a native-audio realtime model.** The
  vertex/gemini native-audio models reject text-only sessions — the socket
  closes `4410`. Leave modalities at the SDK default unless the model is
  explicitly text-capable.
- **Sending a second `session.update` on a live connection.** One setup per
  connection; reconnect to change session config.
- **Holding the realtime WS open as a standing loop.** Helpers run to
  completion (`--timeout` bounded), same rule as `poll_eval_run.py` — no
  skill becomes a server.
- **Persisting or base64-logging audio bytes.** The gateway deliberately
  stores transcripts/input text only; helpers must not undo that by writing
  audio into traces, data assets, or logs. (`--out-wav` output goes only to
  the file the user names.)
- **Assuming BYOK isn't needed.** `gemini` / `vertex` / `openai` providers
  each need their own active BYOK credential; only `hybrie` is keyless.
  `4403` on connect means the credential is missing — route to
  `byok-register`.

## Output contract

`realtime_smoke.py` prints a single JSON summary to stdout —
`{session_ready, audio_bytes, text, input_transcripts, close_reason,
out_wav?}` — and exits non-zero on failure with the gateway's error on
stderr, untouched, so the agent sees exactly what the platform said.
