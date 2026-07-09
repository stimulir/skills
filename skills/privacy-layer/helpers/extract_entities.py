#!/usr/bin/env python3
"""List PII entities found in text via the Stimulir hosted extraction
endpoint, WITHOUT redacting anything.

This is a REAL network call to a real hosted endpoint -- it is not a stub.
POST {STIMULIR_API_URL}/api/v1/privacy/extract with body {"text": ...} and
Authorization: Bearer {STIMULIR_API_KEY}. Same URL builder, env vars, and
auth scheme as evidence-clip's deid_transcript.py and this skill's own
deidentify.py -- same hosted privacy plane.

The response shape for this endpoint is NOT independently confirmed against
source the way deidentify's is -- so this helper does not destructure,
rename, or invent fields. It prints response.json() verbatim to stdout and
does not claim the response carries offsets, original values, or any
specific key beyond what the server actually returns.

Use this to see WHAT would be found before deciding to redact (e.g. to
choose a --keep-tail value, or to confirm entity_types match what
check_capabilities.py reported as supported). It never echoes the input
text back in any log or error message -- only response.json() (which may
itself contain matched values, depending on what the server returns) is
printed, and only to stdout.
"""
import argparse
import json
import os
import sys

import httpx

DEFAULT_API_URL = "https://api.stimulir.com"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text",
        default=None,
        help="raw text to scan for PII entities; if omitted, read from stdin (avoids "
        "putting PII in argv / shell history)",
    )
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    if not text:
        raise SystemExit(
            "extract_entities.py: no text supplied. Pass --text or pipe text on stdin."
        )

    api_url = os.environ.get("STIMULIR_API_URL", DEFAULT_API_URL).rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY")
    if not api_key:
        raise SystemExit(
            "extract_entities.py: STIMULIR_API_KEY is not set. This helper makes a real "
            "call to the Stimulir PII extraction endpoint and needs a real hyb_* key -- "
            "see install.md for where to get one. Refusing to proceed."
        )

    url = f"{api_url}/api/v1/privacy/extract"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"text": text},
            timeout=30.0,
        )
    except httpx.RequestError as e:
        raise SystemExit(f"extract_entities.py: request to {url} failed: {e}")

    if response.status_code != 200:
        body_snippet = response.text[:500] if response.text else ""
        raise SystemExit(
            f"extract_entities.py: {url} returned HTTP {response.status_code}: {body_snippet}"
        )

    data = response.json()

    # No confirmed response shape beyond "it's the extraction result" --
    # print verbatim rather than guessing at field names.
    print(json.dumps(data))
    sys.stderr.write("extract_entities.py: extraction request succeeded\n")


if __name__ == "__main__":
    main()
