#!/usr/bin/env python3
"""Write JSON Schema files for the models (usable for structured-output APIs)."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from schemas.models import ApplicationPackage, DiscoveryResult  # noqa: E402

out = root / "schemas"
for name, model in {"application_package": ApplicationPackage, "discovery_result": DiscoveryResult}.items():
    (out / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2), encoding="utf-8")
    print("wrote", out / f"{name}.schema.json")
