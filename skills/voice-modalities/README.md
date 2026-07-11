# voice-modalities

Wire an application onto stimulir's voice lane -- for Codex / Claude Code.
One realtime WebSocket (`WS /api/v1/inference/realtime`) covers all three
modalities in a single session, omni-model native: speech-to-speech
(`send_audio` in, `AudioDelta` out), live transcription (gateway-injected
`InputTranscript` events), and text-to-speech (`send_context` in, verbatim
speech out under a TTS instruction -- verified character-exact). Four
providers via `?provider=`: `gemini`/`vertex`/`openai` need a BYOK
credential, `hybrie` is keyless (in-cluster Qwen2.5-Omni). The helper uses
the Python SDK's `stimulir[realtime]` extra. Batch audio (stored files,
bulk synthesis) is the chat lane's job via audio input parts -- not served
yet; the gateway's legacy OpenAI-compat audio REST endpoints are not the
stimulir path. Hard rules: bounded sessions only (no helper holds the
WebSocket open as a server) and audio bytes are never persisted or logged
(transcripts only, matching the gateway).

## Quick start

```bash
uv sync    # stimulir[realtime]

# speech-to-speech smoke -- one bounded turn, prints a JSON summary
python helpers/realtime_smoke.py --provider vertex --say "Say exactly: VOICE LANE OK"

# text-to-speech through the same lane
python helpers/realtime_smoke.py --provider vertex \
  --instructions "You are a text-to-speech engine. Speak the user's text exactly as written, nothing else." \
  --say "Hello from stimulir" --out-wav hello.wav

# speech-to-text of a short clip (16 kHz mono PCM16 WAV)
python helpers/realtime_smoke.py --provider vertex --wav clip.wav
```

See [`SKILL.md`](./SKILL.md) for provider/model selection, the event
protocol and close codes, metering, and the anti-patterns;
[`install.md`](./install.md) for setup.
