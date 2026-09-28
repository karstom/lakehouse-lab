"""`lab-token`: print the logged-in user's access token (for curl, CLIs, env vars).

    lab-token                   the token (valid for at least 2 minutes)
    lab-token --min-ttl 1800    valid for at least 30 minutes (long-running commands)
    lab-token --claims          the token's claims as JSON (not verified; for inspection)
"""
import argparse
import json
import sys
import time

from .token import DEFAULT_MIN_TTL, LabTokenError, lab_token, token_claims


def main(argv=None):
    p = argparse.ArgumentParser(prog="lab-token", description=__doc__.splitlines()[0])
    p.add_argument("--min-ttl", type=int, default=DEFAULT_MIN_TTL,
                   help="seconds the token must still be valid (default %(default)s)")
    p.add_argument("--claims", action="store_true", help="print the decoded claims instead")
    a = p.parse_args(argv)
    try:
        tok = lab_token(min_ttl=a.min_ttl)
    except LabTokenError as e:
        print(f"lab-token: {e}", file=sys.stderr)
        return 1
    if a.claims:
        c = token_claims(tok)
        c["_expires_in_s"] = int(c.get("exp", 0) - time.time())
        print(json.dumps(c, indent=2, sort_keys=True))
    else:
        print(tok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
