"""ConfigForge command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import (
    ConfigForgeError,
    Layer,
    __version__,
    decrypt_secrets,
    encrypt_secrets,
    forge,
    generate_key,
    load_schema,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="configforge",
        description="Layered, schema-aware configuration with encrypted secrets.",
    )
    parser.add_argument("--version", action="version", version=f"configforge {__version__}")
    parser.add_argument(
        "-l", "--layer", action="append", default=[], metavar="FILE",
        help="JSON layer file (may be repeated; later wins).",
    )
    parser.add_argument(
        "--env-prefix", default=None, metavar="PREFIX",
        help="Prefix for environment variables to fold in (e.g. APP__).",
    )
    parser.add_argument(
        "--schema", default=None, metavar="FILE", help="JSON schema to validate against."
    )
    parser.add_argument(
        "--secrets", default=None, metavar="FILE",
        help="Fernet-encrypted JSON secrets file to decrypt and merge.",
    )
    parser.add_argument(
        "--key", default=None, metavar="B64",
        help="32-byte url-safe base64 Fernet key for --secrets.",
    )
    parser.add_argument(
        "--generate-key", action="store_true",
        help="Print a fresh Fernet key to stdout and exit.",
    )
    parser.add_argument(
        "--encrypt-secrets", default=None, metavar="FILE",
        help="Encrypt a JSON file (given as FILE) to a Fernet token on stdout "
        "using --key (for testing/round-trips).",
    )
    parser.add_argument(
        "--no-fail-on-conflict", action="store_true",
        help="Do not error on scalar conflicts; later value wins.",
    )
    parser.add_argument(
        "-o", "--output", default=None, metavar="FILE",
        help="Write resolved JSON here instead of stdout.",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress non-JSON stderr notices."
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.generate_key:
        try:
            print(generate_key())
        except ConfigForgeError as exc:
            print(f"configforge: error: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.encrypt_secrets:
        try:
            with open(args.encrypt_secrets, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ConfigForgeError("secrets source must be a JSON object")
            if not args.key:
                raise ConfigForgeError("--key is required to encrypt")
            token = encrypt_secrets(data, args.key)
            sys.stdout.buffer.write(token)
            sys.stdout.buffer.write(b"\n")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"configforge: error: {exc}", file=sys.stderr)
            return 1
        except ConfigForgeError as exc:
            print(f"configforge: error: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        layers = [Layer.from_json_file(p) for p in args.layer]
        schema = load_schema(args.schema) if args.schema else None
        secrets = None
        if args.secrets:
            key = args.key or os.environ.get("CONFIGFORGE_KEY")
            if not key:
                raise ConfigForgeError("--key (or CONFIGFORGE_KEY env) is required to decrypt")
            secrets = decrypt_secrets(args.secrets, key=key)

        config = forge(
            *layers,
            schema=schema,
            secrets=secrets,
            env_prefix=args.env_prefix,
            fail_on_conflict=not args.no_fail_on_conflict,
        )
    except ConfigForgeError as exc:
        print(f"configforge: error: {exc}", file=sys.stderr)
        return 1

    out = config.to_json()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        if not args.quiet:
            print(f"configforge: wrote resolved config to {args.output}", file=sys.stderr)
    else:
        print(out)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _run(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
