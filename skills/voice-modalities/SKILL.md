---
name: voice-modalities
description: Wire an application onto stimulir's three voice lanes — live speech-to-speech over the realtime WebSocket, speech-to-text transcription, and text-to-speech synthesis. Use when a user wants to add voice to an app on stimulir, run a live voice session, transcribe audio, synthesize speech, or figure out which model/endpoint serves which audio modality.
---

# Voice Modalities

Three separate lanes, three separate maturity levels. This skill exists
because the lanes cannot be discovered from any single place: realtime is
documented but STT/TTS exist only at the raw gateway, the Python SDK covers
realtime only (behind an extra), and the CLI has no voice commands at all.
Everything below was verified against the live gateway — including the current
status of each lane, so an agent doesn't burn a session rediscovering it.

## The three lanes

| Lane | Endpoint | SDK | Status (verified) |
|---|---|---|---|
| Realtime STS + TTS | `WS /api/v1/inference/realtime` | `stimulir.realtime.RealtimeClient` | **Working** — live session returns spoken audio; text-in gives verbatim speech-out |
| STT | `POST /api/v1/inference/audio/transcriptions` | none (httpx) | **Temporarily unavailable** — the platform returns a clear 400 for every request this release; the request shape below is stable |
| TTS | `POST /api/v1/inference/audio/speech` | none (httpx) | **REST lane temporarily unavailable — use realtime-as-TTS below, verified working** |

All three authenticate with the workspace `hyb_*` key (`Authorization:
Bearer`). The realtime WS also accepts `?api_key=` as a query param for
clients that cannot set headers.

Run the lanes in this order when integrating: realtime first (it works,
proves the key/workspace, and covers speech-out via realtime-as-TTS), then keep the STT/TTS helpers wired so they light
up when the platform enables those lanes — the request shapes below
are correct and stable; only the upstream serving is pending.

## Placement rationale

Assumes `connect` has already run (CLI installed, authenticated, workspace
selected) so a `hyb_*` key exists. Unlike most skills in this collection,
the helpers here can NOT shell out to the `stimulir` CLI — it has no voice
commands today. `speak.py` and `transcribe.py` call the gateway directly
with httpx (the `privacy-layer` pattern); `realtime_smoke.py` uses the
Python SDK's realtime extra rather than hand-rolling the WebSocket
protocol. This is the third non-stdlib skill in the collection.

## Preflight

```bash
python3 --version                      # 3.10+
uv sync                                # installs httpx + stimulir[realtime]
test -n "$STIMULIR_API_KEY" || grep -q api_key ~/.stimulir/credentials.json
```

## Lane 1 — Realtime speech-to-speech (working)

One WebSocket, bidirectional audio, server-side turn detection, per-session
minute metering (`modality: "voice_realtime"`).

**Provider selection** via `?provider=` — this decides everything:

- `gemini` / `vertex` / `openai` — requires an **active BYOK credential for
  that provider** on the workspace (see `byok-register`). Vertex accepts a
  service-account JSON or an Express-Mode API key. Default models:
  `gemini-2.5-flash-native-audio-preview-12-2025` (gemini),
  `gemini-live-2.5-flash-preview-native-audio-09-2025` (vertex),
  `gpt-realtime` (openai). Override with `?model=`.
- `hybrie` — **no BYOK needed**; bridges to the in-cluster HybrIE engine
  (Qwen2.5-Omni). Availability depends on the deployment running the omni
  engine.

**Audio format**: 16 kHz mono PCM16 in; the SDK exposes
`INPUT_AUDIO_SAMPLE_RATE` / `OUTPUT_AUDIO_SAMPLE_RATE` constants — read
them rather than hardcoding.

**SDK usage** (the pattern `realtime_smoke.py` wraps):

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
            log(event.text)      # gateway injects input transcription
        elif isinstance(event, ResponseDone):
            break
```

Smoke it bounded (never leave the socket open past the check):

```bash
python helpers/realtime_smoke.py --provider vertex --say "Say exactly: VOICE LANE OK"
```

**Close codes** when the connection drops instead of erroring in-band:
`4400` bad request, `4401` unauthorized, `4403` forbidden (missing BYOK for
the chosen provider), `4410` upstream provider rejected the session — check
the model id and modalities first, it is usually one of those.

## Lane 2 — STT transcription (request shape correct, lane gated)

```bash
python helpers/transcribe.py recording.wav --model whisper-1 [--language en]
```

OpenAI-shape multipart: `file` + `model` (+ optional `language`, `prompt`,
`response_format`, `temperature`). Transcript text is trace-captured;
**audio bytes are never stored**. Metering: `modality: "stt"`, cost 0 with
`"pricing": "unrated"`. Currently unavailable — the helper surfaces the
platform's 400 verbatim so the state is obvious rather than mysterious.

## Lane 3 — TTS synthesis (request shape correct, upstream broken)

```bash
python helpers/speak.py "Text to speak" --model tts-1 --voice alloy --out speech.mp3
```

OpenAI-shape JSON: `model` + `input` (+ passthrough fields like `voice`).
Returns binary audio verbatim (default `audio/mpeg`). Input text is
trace-captured; audio bytes never stored. Metering: `modality: "tts"`,
`characters` in metadata, cost 0 unrated. Currently unavailable — the helper prints the
platform's error verbatim. When it ships this is the batch/high-volume
lane: managed (no BYOK), character-metered, mp3 out.

**Working today: realtime-as-TTS.** The realtime lane accepts text in and
returns spoken audio out, which is functionally TTS — verified: verbatim
speech, playable 24 kHz WAV. Pin the model to verbatim delivery through the
instructions and write the response audio with `--out-wav`:

```bash
python helpers/realtime_smoke.py --provider vertex \
  --instructions "You are a text-to-speech engine. Speak the user's text exactly as written, nothing else." \
  --say "Text you want spoken." \
  --out-wav speech.wav
```

Trade-offs vs the REST lane (when it is fixed): an LLM speaking under
instruction rather than a deterministic TTS engine (verbatim in practice,
probabilistic in principle); billed as `voice_realtime` minutes rather than
characters; a WS session per utterance; PCM16/WAV out rather than mp3; and
the vertex/gemini/openai providers need BYOK where the REST lane is
managed. For batch or high-volume synthesis prefer the REST lane once
unblocked; for interactive apps that already hold a realtime session, this
is not a workaround at all — it is simply the lane's normal output.

## Anti-patterns (do NOT do)

- **Appending `/v1` to the audio paths.** `chat/completions` has an
  OpenAI-compat `/v1/...` alias; the two audio routes do not. A base URL
  ending in `.../inference/v1` 404s on audio.
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
  audio into traces, data assets, or logs.
- **Faking STT by base64-ing audio into the chat lane.** Multimodal chat
  vision parts are for images; audio goes through the audio lanes.
- **Assuming BYOK isn't needed.** `gemini` / `vertex` / `openai` realtime
  providers each need their own active BYOK credential; only `hybrie` is
  keyless. `4403` on connect means the credential is missing — route to
  `byok-register`.

## Output contract

Every helper prints a single JSON object to stdout (transcription JSON,
TTS metadata `{bytes, content_type, out}`, or the realtime summary
`{session_ready, audio_bytes, text, input_transcripts, close_reason}`) and
exits non-zero on failure with the gateway's error JSON on stderr —
untouched, so the agent sees exactly what the platform said.
