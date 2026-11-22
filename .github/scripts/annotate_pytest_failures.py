"""Turn a pytest JUnit report into GitHub annotations, so a failing test is readable
from the pull request checks (and from the public API) without opening the raw log."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_ANNOTATIONS = 10


def escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text: str) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def main(report: str) -> int:
    path = Path(report)
    if not path.exists():
        print("::warning::pytest failed before it wrote a report (a crash or a collection error).")
        return 0
    shown = 0
    for case in ET.parse(path).getroot().iter("testcase"):
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is None:
                continue
            raw = f"{node.get('message') or ''}\n{node.text or ''}"
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            text = " | ".join(lines)[:1500]
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            print(f"::error title={escape_property('pytest failed: ' + name[:110])}::{escape_data(text)}")
            shown += 1
        if shown >= MAX_ANNOTATIONS:
            break
    if shown == 0:
        print("::warning::pytest failed but its report lists no failing test case.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "pytest-report.xml"))
