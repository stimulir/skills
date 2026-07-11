#!/usr/bin/env python3
"""Speech-to-text via POST {STIMULIR_API_URL}/api/v1/inference/audio/transcriptions.

OpenAI-shape multipart (file + model, optional language/prompt/
response_format/temperature); the gateway forwards the upstream JSON
verbatim, which this helper prints to stdout untouched. Transcript text is
trace-captured server-side; the audio bytes are never stored.

Direct httpx (privacy-layer pattern) because the stimulir CLI has no voice
commands to shell out to. NOTE the path has no /v1 OpenAI-compat alias.

Known state at authoring time: this REST lane is temporarily unavailable
platform-side and returns a clear 400 for every request this release. The
request shape here is correct and stable; the helper surfaces the
platform's error verbatim on stderr so the state is obvious.
"""
import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", help="Audio file to transcribe (wav/mp3/m4a/...).")
    parser.add_argument("--model", required=True, help="STT model id (e.g. whisper-1; validated upstream).")
    parser.add_argument("--language", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--response-format", default=None, help="json | text | verbose_json | ...")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    api_url = os.environ.get("STIMULIR_API_URL", "https://api.stimulir.com").rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY", "")
    if not api_key:
        print("STIMULIR_API_KEY is not set", file=sys.stderr)
        raise SystemExit(1)

    path = Path(args.file)
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    data = {"model": args.model}
    for field in ("language", "prompt", "temperature"):
        value = getattr(args, field)
        if value is not None:
            data[field] = str(value)
    if args.response_format is not None:
        data["response_format"] = args.response_format

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as fh:
        response = httpx.post(
            f"{api_url}/api/v1/inference/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (path.name, fh, content_type)},
            data=data,
            timeout=args.timeout,
        )
    if response.status_code >= 400:
        sys.stderr.write(response.text[:2000] + "\n")
        raise SystemExit(1)
    print(json.dumps(response.json()) if response.headers.get("content-type", "").startswith("application/json") else response.text)


if __name__ == "__main__":
    main()
