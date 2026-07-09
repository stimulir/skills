#!/usr/bin/env python3
"""Discover what entity types / methods the Stimulir hosted privacy layer
currently supports, before deciding a redaction strategy.

This is a REAL network call to a real hosted endpoint -- it is not a stub.
GET {STIMULIR_API_URL}/api/v1/privacy/capabilities with
Authorization: Bearer {STIMULIR_API_KEY}. Same URL builder, env vars, and
auth scheme as this skill's deidentify.py and extract_entities.py -- same
hosted privacy plane.

The response shape for this endpoint is NOT independently confirmed against
source -- so this helper does not destructure, rename, or invent fields. It
prints response.json() verbatim to stdout. Whatever entity types / methods
it reports, treat as the ground truth for what deidentify.py's --method can
actually do and what extract_entities.py can actually find -- don't assume
capabilities beyond what this call reports.

Takes no arguments -- capabilities are a property of the service, not the
input text.
"""
import argparse
import json
import os
import sys

import httpx

DEFAULT_API_URL = "https://api.stimulir.com"


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    api_url = os.environ.get("STIMULIR_API_URL", DEFAULT_API_URL).rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY")
    if not api_key:
        raise SystemExit(
            "check_capabilities.py: STIMULIR_API_KEY is not set. This helper makes a real "
            "call to the Stimulir privacy capabilities endpoint and needs a real hyb_* "
            "key -- see install.md for where to get one. Refusing to proceed."
        )

    url = f"{api_url}/api/v1/privacy/capabilities"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
    except httpx.RequestError as e:
        raise SystemExit(f"check_capabilities.py: request to {url} failed: {e}")

    if response.status_code != 200:
        body_snippet = response.text[:500] if response.text else ""
        raise SystemExit(
            f"check_capabilities.py: {url} returned HTTP {response.status_code}: {body_snippet}"
        )

    data = response.json()

    # No confirmed response shape -- print verbatim rather than guessing at
    # field names.
    print(json.dumps(data))
    sys.stderr.write("check_capabilities.py: capabilities request succeeded\n")


if __name__ == "__main__":
    main()
