#!/usr/bin/env python3
"""One-time Open Prices auth bootstrap.

Prompts for an Open Food Facts password (via getpass — never echoed, never
stored, never passed on the command line), exchanges it at
``POST /api/v1/auth`` for a session token, and writes ONLY the token to
``~/.config/inventory-md/openprices-token`` (mode 0600). The token has no
intrinsic expiry, so this is run once; the publisher reads the file.

Run interactively:  python scripts/op_auth.py [--username tobixen] [--env org]
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import niquests as requests

BASES = {"org": "https://prices.openfoodfacts.org", "net": "https://prices.openfoodfacts.net"}
TOKEN_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "inventory-md" / "openprices-token"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", default="tobixen")
    parser.add_argument("--env", choices=["org", "net"], default="org")
    args = parser.parse_args()

    password = getpass.getpass(f"Open Prices password for {args.username} ({args.env}): ")
    if not password:
        sys.exit("no password entered")

    resp = requests.post(
        f"{BASES[args.env]}/api/v1/auth",
        data={"username": args.username, "password": password},
        timeout=30,
    )
    if resp.status_code != 200:
        sys.exit(f"auth failed: HTTP {resp.status_code} {resp.text[:200]}")
    token = resp.json().get("access_token")
    if not token:
        sys.exit(f"no access_token in response: {resp.text[:200]}")

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    TOKEN_PATH.chmod(0o600)
    print(f"OK — token saved to {TOKEN_PATH} (user {token.split('__')[0]})")


if __name__ == "__main__":
    main()
