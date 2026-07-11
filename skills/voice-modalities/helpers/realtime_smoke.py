#!/usr/bin/env python3
"""Bounded realtime speech-to-speech smoke check via the Stimulir SDK.

Connects to WS {realtime_url}?provider=..., runs ONE turn (either a text
context prompt via --say or a PCM16 WAV file via --wav), collects events
until ResponseDone or --timeout, prints a JSON summary, and exits. It never
holds the socket open past the check — no skill becomes a server.

Uses stimulir[realtime] (RealtimeClient) rather than hand-rolling the
WebSocket protocol: the SDK owns setup()'s once-only guard, the event
schema, and the auth handshake. This helper adds only bounding and
reporting; which provider/model to use is the agent's judgment (SKILL.md).

Audio bytes are counted and never printed or traced; pass --out-wav to
write the spoken response to a WAV file you name — which makes this helper
double as working text-to-speech (text in via --say, speech out) while the
dedicated /audio/speech REST lane is blocked upstream. For verbatim TTS use
--instructions to pin the model to speaking the text exactly.
"""
import argparse
import asyncio
import json
import os
import sys
import wave


def read_wav_pcm16(path: str, expected_rate: int) -> bytes:
    with wave.open(path, "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
            raise SystemExit(f"--wav must be 16-bit mono PCM (got {wav.getnchannels()}ch/{wav.getsampwidth() * 8}-bit)")
        if wav.getframerate() != expected_rate:
            raise SystemExit(f"--wav must be {expected_rate} Hz (got {wav.getframerate()} Hz); resample first")
        return wav.readframes(wav.getnframes())


async def run(args: argparse.Namespace) -> dict:
    from stimulir.realtime import (
        INPUT_AUDIO_SAMPLE_RATE,
        OUTPUT_AUDIO_SAMPLE_RATE,
        AudioDelta,
        InputTranscript,
        RealtimeClient,
        ResponseDone,
        SessionReady,
        TextDelta,
    )

    base = args.url or os.environ.get("STIMULIR_REALTIME_URL")
    if base is None:
        api = os.environ.get("STIMULIR_API_URL", "https://api.stimulir.com")
        scheme = "wss" if api.startswith("https") else "ws"
        base = f"{scheme}://{api.split('://', 1)[1]}/api/v1/inference/realtime"
    url = f"{base}{'&' if '?' in base else '?'}provider={args.provider}"
    if args.model:
        url += f"&model={args.model}"

    client = RealtimeClient(realtime_url=url, instructions=args.instructions)
    summary = {"session_ready": False, "audio_bytes": 0, "text": "", "input_transcripts": [], "close_reason": None}
    async with client.connect() as conn:
        await conn.setup()
        if args.wav:
            await conn.send_audio(read_wav_pcm16(args.wav, INPUT_AUDIO_SAMPLE_RATE))
            await conn.commit()
        else:
            await conn.send_context(args.say)
            await conn.create_response()

        text_parts: list[str] = []
        audio_parts: list[bytes] = []

        async def consume() -> None:
            async for event in conn.events():
                if isinstance(event, SessionReady):
                    summary["session_ready"] = True
                elif isinstance(event, TextDelta):
                    text_parts.append(event.delta)
                elif isinstance(event, AudioDelta):
                    summary["audio_bytes"] += len(event.pcm16)
                    if args.out_wav:
                        audio_parts.append(event.pcm16)
                elif isinstance(event, InputTranscript):
                    summary["input_transcripts"].append(event.text)
                elif isinstance(event, ResponseDone):
                    return

        try:
            await asyncio.wait_for(consume(), timeout=args.timeout)
        except asyncio.TimeoutError:
            summary["close_reason"] = f"timeout after {args.timeout}s"
        summary["text"] = "".join(text_parts)
        if args.out_wav and audio_parts:
            with wave.open(args.out_wav, "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(OUTPUT_AUDIO_SAMPLE_RATE)
                out.writeframes(b"".join(audio_parts))
            summary["out_wav"] = args.out_wav
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", default="vertex", help="gemini | vertex | openai | hybrie")
    parser.add_argument("--model", default=None, help="Override the provider's default realtime model.")
    parser.add_argument("--say", default="Say exactly: VOICE LANE OK", help="Text context for the turn (default smoke phrase).")
    parser.add_argument("--wav", default=None, help="16 kHz mono PCM16 WAV to send instead of --say.")
    parser.add_argument("--instructions", default="You are a concise voice assistant.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Hard bound on the event loop (seconds).")
    parser.add_argument("--url", default=None, help="Full realtime WS URL override (query params appended).")
    parser.add_argument("--out-wav", default=None, help="Write the spoken response to this WAV path (realtime-as-TTS).")
    args = parser.parse_args()
    try:
        summary = asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001 — surface the gateway error verbatim
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(summary))
    if not summary["session_ready"] or (summary["audio_bytes"] == 0 and not summary["text"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
