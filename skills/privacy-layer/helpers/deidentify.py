#!/usr/bin/env python3
"""Redact/mask PII in agent-collected text via the Stimulir hosted
de-identification endpoint.

This is a REAL network call to a real hosted endpoint -- it is not a stub.
POST {STIMULIR_API_URL}/api/v1/privacy/deidentify with body {"text": ...,
"method": {"kind": ..., ...}} and Authorization: Bearer {STIMULIR_API_KEY}.
Same URL builder, env vars, and auth scheme as evidence-clip's
deid_transcript.py -- this is the same hosted privacy plane, confirmed
against the HybrIE Rust source (hybrie-server/src/api/privacy.rs):

    struct DeidentifyRequest { text: String, method: MethodSpec, ... }

`MethodSpec` is a serde internally-tagged enum (`#[serde(tag = "kind")]`) --
it deserializes ONLY from a nested object, never a bare string. Sending
`"method": "mask"` fails to deserialize entirely (falls through to the
`#[serde(default)]` Replace variant server-side, silently ignoring the
caller's choice). The correct shape for the `mask` kind is:

    {"text": ..., "method": {"kind": "mask", "mask_char": "*", "keep_tail": 4}}

Valid `kind` values (all snake_case): replace, redact, mask, hash_sha256,
hash_sha512, encrypt, decrypt, keep, replace_consistent. Only `mask` uses
`mask_char`/`keep_tail`; passing them with any other kind is rejected here
before the request is even sent, rather than silently ignored server-side.

Response shape (DeidentifyResponse struct):

    {"text": <redacted text>, "redactions": <int>, "entity_types": [<str>, ...]}

This helper does not decide *when* to redact, *what* counts as sensitive,
or *whether* a zero-redaction response means the text is safe to persist --
that judgment belongs to the agent orchestrating this skill (see SKILL.md).
It only makes the call and prints the response as JSON to stdout.

It also never echoes the pre-redaction input text anywhere -- not to
stdout, not to stderr, not in an error message -- to avoid defeating the
purpose of the call it wraps.
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
        help="raw text to de-identify; if omitted, read from stdin (avoids putting PII "
        "in argv / shell history)",
    )
    parser.add_argument(
        "--method",
        default=None,
        choices=[
            "replace",
            "redact",
            "mask",
            "hash_sha256",
            "hash_sha512",
            "encrypt",
            "decrypt",
            "keep",
            "replace_consistent",
        ],
        help="redaction method kind; omitted from the request body if not given, so the "
        "server's default (replace) applies. Only 'mask' accepts --mask-char/--keep-tail.",
    )
    parser.add_argument(
        "--mask-char",
        default=None,
        help="character used to mask matched spans when --method mask; omitted from the "
        "request body if not given",
    )
    parser.add_argument(
        "--keep-tail",
        type=int,
        default=None,
        help="number of trailing characters to leave unmasked (e.g. last 4 digits of an "
        "account number); omitted from the request body if not given",
    )
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    if not text:
        raise SystemExit(
            "deidentify.py: no text supplied. Pass --text or pipe text on stdin."
        )

    api_url = os.environ.get("STIMULIR_API_URL", DEFAULT_API_URL).rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY")
    if not api_key:
        raise SystemExit(
            "deidentify.py: STIMULIR_API_KEY is not set. This helper makes a real call "
            "to the Stimulir de-identification endpoint and needs a real hyb_* key -- "
            "see install.md for where to get one. Refusing to proceed."
        )

    if args.method != "mask" and (args.mask_char is not None or args.keep_tail is not None):
        raise SystemExit(
            "deidentify.py: --mask-char/--keep-tail only apply to --method mask "
            f"(got --method {args.method!r})."
        )

    body = {"text": text}
    if args.method is not None:
        # MethodSpec is a serde internally-tagged enum (`#[serde(tag = "kind")]`) --
        # it only deserializes from a nested object, never a bare string.
        method = {"kind": args.method}
        if args.mask_char is not None:
            method["mask_char"] = args.mask_char
        if args.keep_tail is not None:
            method["keep_tail"] = args.keep_tail
        body["method"] = method

    url = f"{api_url}/api/v1/privacy/deidentify"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=30.0,
        )
    except httpx.RequestError as e:
        raise SystemExit(f"deidentify.py: request to {url} failed: {e}")

    if response.status_code != 200:
        body_snippet = response.text[:500] if response.text else ""
        raise SystemExit(
            f"deidentify.py: {url} returned HTTP {response.status_code}: {body_snippet}"
        )

    data = response.json()

    # Pass through verbatim -- only these three fields are confirmed against
    # the server response shape. Don't invent or rename fields.
    result = {
        "text": data["text"],
        "redactions": data.get("redactions", 0),
        "entity_types": data.get("entity_types", []),
    }
    print(json.dumps(result))
    sys.stderr.write(
        f"deidentify.py: redacted {result['redactions']} span(s), "
        f"entity types: {result['entity_types']}\n"
    )


if __name__ == "__main__":
    main()
