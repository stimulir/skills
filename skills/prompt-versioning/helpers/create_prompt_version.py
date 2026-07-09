#!/usr/bin/env python3
"""Create a prompt version, or update an existing version's metadata, via the
stimulir CLI.

Two modes, matching the two real CLI subcommands -- this helper does not
merge them into one implicit behavior:

  create  ->  `stimulir prompts create --key K --content ... [--label L] --json`
              Always produces a NEW version (version 1 if the key is new,
              version N+1 if the key already exists). Content is required
              (via --content or --file). This is additive: it never moves an
              existing label unless you explicitly pass --label, and by
              stimulir's own semantics a fresh, un-labeled version does not
              affect what any environment currently serves.

  update  ->  `stimulir prompts update KEY VERSION [--name ...] [--notes ...]
              [--active/--inactive] --json`
              Metadata only. Prompt CONTENT is immutable once a version
              exists -- there is no "edit content" mode here. To change
              content, create a new version instead.

Both modes are non-destructive in the sense that neither one silently moves
a `prod` (or any) label -- promotion is a distinct, explicit action that
lives in label_prompt.py. Passing --label here only sets the label on a
BRAND NEW version being created, which is a normal part of `create`'s own
surface (e.g. seeding a fresh version straight to "dev" or "staging"); it is
still the caller's explicit, typed-out choice, not an implicit side effect.
"""
import argparse
import json
import subprocess


def run_create(args) -> dict:
    if not args.content and not args.file:
        raise SystemExit(
            "create_prompt_version.py: create mode needs --content or --file "
            "(prompt body). Refusing to create an empty-content version."
        )
    if args.content and args.file:
        raise SystemExit("create_prompt_version.py: pass --content or --file, not both.")

    cmd = ["stimulir", "prompts", "create", "--key", args.key]
    if args.content:
        cmd += ["--content", args.content]
    if args.file:
        cmd += ["--file", args.file]
    if args.name:
        cmd += ["--name", args.name]
    if args.type:
        cmd += ["--type", args.type]
    if args.label:
        cmd += ["--label", args.label]
    if args.notes:
        cmd += ["--notes", args.notes]
    cmd.append("--json")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"create_prompt_version.py: create failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"create_prompt_version.py: could not parse JSON from create: {e}\n"
            f"stdout was: {proc.stdout[:500]}"
        )


def run_update(args) -> dict:
    cmd = ["stimulir", "prompts", "update", args.key, str(args.version)]
    if args.name:
        cmd += ["--name", args.name]
    if args.notes:
        cmd += ["--notes", args.notes]
    if args.active:
        cmd.append("--active")
    elif args.inactive:
        cmd.append("--inactive")
    cmd.append("--json")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"create_prompt_version.py: update failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"create_prompt_version.py: could not parse JSON from update: {e}\n"
            f"stdout was: {proc.stdout[:500]}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_create = sub.add_parser("create", help="create a new prompt version (new key or existing key)")
    p_create.add_argument("--key", required=True, help="stable prompt key")
    p_create.add_argument("--content", default=None, help="prompt body (mutually exclusive with --file)")
    p_create.add_argument("--file", default=None, help="path to read prompt body from")
    p_create.add_argument("--name", default=None, help="display name")
    p_create.add_argument("--type", default=None, help="optional prompt type tag")
    p_create.add_argument("--label", default=None, help="label to attach to this version, e.g. dev")
    p_create.add_argument("--notes", default=None, help="change notes for this version")

    p_update = sub.add_parser("update", help="update metadata on an existing version (content is immutable)")
    p_update.add_argument("--key", required=True, help="prompt key")
    p_update.add_argument("--version", required=True, type=int, help="version number to update")
    p_update.add_argument("--name", default=None, help="display name")
    p_update.add_argument("--notes", default=None, help="change notes")
    active_group = p_update.add_mutually_exclusive_group()
    active_group.add_argument("--active", action="store_true", help="mark this version active")
    active_group.add_argument("--inactive", action="store_true", help="mark this version inactive")

    args = parser.parse_args()

    if args.mode == "create":
        result = run_create(args)
    else:
        result = run_update(args)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
