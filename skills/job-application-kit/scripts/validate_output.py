#!/usr/bin/env python3
"""Validate skill output JSON against the typed schemas.

Usage:
    python scripts/validate_output.py package  path/to/package.json
    python scripts/validate_output.py discovery path/to/discovery.json
Exit code 0 = valid, 1 = invalid (errors printed one per line).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pydantic import ValidationError  # noqa: E402
from schemas.models import ApplicationPackage, DiscoveryResult  # noqa: E402

MODELS = {"package": ApplicationPackage, "discovery": DiscoveryResult}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in MODELS:
        print(__doc__)
        return 2
    data = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    try:
        MODELS[argv[1]].model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            print(f"INVALID {loc}: {err['msg']}")
        return 1
    print(f"OK: {argv[2]} is a valid {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
