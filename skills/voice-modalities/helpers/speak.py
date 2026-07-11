#!/usr/bin/env python3
"""Text-to-speech via POST {STIMULIR_API_URL}/api/v1/inference/audio/speech.

OpenAI-shape JSON body ({"model", "input", extra fields like "voice"
forwarded verbatim}); the gateway returns the upstream binary audio
unmodified (default audio/mpeg). Audio is written to --out; only metadata
JSON goes to stdout. Input text is trace-captured server-side; audio bytes
are never stored — this helper doesn't log them either.

Direct httpx (privacy-layer pattern) because the stimulir CLI has no voice
commands to shell out to. NOTE the path has no /v1 OpenAI-compat alias —
do not point an OpenAI SDK client at it.

Known upstream state at authoring time: HybrIE's Runware TTS adapter sends
a non-UUIDv4 taskUUID and every request 400s. This helper's request shape
is correct; it surfaces that backend error verbatim on stderr so the state
is obvious rather than mysterious.
"""
import argparse
import json
import os
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Text to synthesize.")
    parser.add_argument("--model", required=True, help="TTS model id (validated by the upstream engine, not the gateway).")
    parser.add_argument("--voice", default=None, help="Voice id, forwarded verbatim when set.")
    parser.add_argument("--response-format", default=None, help="Audio format, forwarded verbatim when set.")
    parser.add_argument("--out", default="speech.mp3", help="Where to write the binary audio.")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    api_url = os.environ.get("STIMULIR_API_URL", "https://api.stimulir.com").rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY", "")
    if not api_key:
        print("STIMULIR_API_KEY is not set", file=sys.stderr)
        raise SystemExit(1)

    body = {"model": args.model, "input": args.input}
    if args.voice:
        body["voice"] = args.voice
    if args.response_format:
        body["response_format"] = args.response_format

    response = httpx.post(
        f"{api_url}/api/v1/inference/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json=body,
        timeout=args.timeout,
    )
    if response.status_code >= 400:
        sys.stderr.write(response.text[:2000] + "\n")
        raise SystemExit(1)

    with open(args.out, "wb") as fh:
        fh.write(response.content)
    print(json.dumps({
        "bytes": len(response.content),
        "content_type": response.headers.get("content-type", "audio/mpeg"),
        "out": args.out,
    }))


if __name__ == "__main__":
    main()
