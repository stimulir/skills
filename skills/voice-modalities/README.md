# voice-modalities

Wire an application onto stimulir's three voice lanes -- for Codex / Claude
Code. Live speech-to-speech runs over `WS /api/v1/inference/realtime`
(four providers: `gemini`/`vertex`/`openai` need BYOK, `hybrie` is keyless)
via the Python SDK's `stimulir[realtime]` extra; transcription and speech
synthesis are raw gateway REST lanes (`/audio/transcriptions`,
`/audio/speech`) with no SDK or CLI coverage, so the two REST helpers call
them directly with httpx. Every lane was verified live at authoring time and
[`SKILL.md`](./SKILL.md) records the honest per-lane status -- realtime
works end to end (including verbatim text-to-speech through the same
session); the STT and TTS REST lanes are temporarily unavailable
platform-side, with the correct request shapes wired so both light up the
moment they ship. Hard rules: bounded sessions only (no helper
holds the WebSocket open as a server), audio bytes are never persisted or
logged (transcripts only, matching the gateway), and the audio paths have no
`/v1` OpenAI-compat alias.

## Quick start

```bash
uv sync    # httpx + stimulir[realtime]

# 1. realtime smoke -- one bounded turn, prints a JSON summary
python helpers/realtime_smoke.py --provider vertex --say "Say exactly: VOICE LANE OK"

# 2. text-to-speech, working today via the realtime lane
python helpers/realtime_smoke.py --provider vertex \
  --instructions "You are a text-to-speech engine. Speak the user's text exactly as written, nothing else." \
  --say "Hello from stimulir" --out-wav hello.wav

# 3. REST lanes (temporarily unavailable platform-side; shapes are stable)
python helpers/transcribe.py recording.wav --model whisper-1
python helpers/speak.py "Hello from stimulir" --model tts-1 --voice alloy --out hello.mp3
```

See [`SKILL.md`](./SKILL.md) for provider/model selection, the realtime
event protocol and close codes, metering semantics per lane, and the
anti-patterns; [`install.md`](./install.md) for setup.
