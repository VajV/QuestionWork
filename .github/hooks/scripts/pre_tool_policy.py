import json
import re
import sys
from typing import Any


DANGEROUS_PATTERNS = [
    r"git\s+reset\s+--hard",
    r"git\s+checkout\s+--",
    r"git\s+clean\s+-fd",
    r"Remove-Item\b.*-Recurse\b.*-Force",
]

GENERATED_PATH_MARKERS = [
    ".next-dev",
    "\\.venv\\",
    "/.venv/",
    "playwright-audit-artifacts",
]


def flatten_strings(value: Any) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            items.extend(flatten_strings(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(flatten_strings(child))
    return items


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
                "stopReason": reason,
            }
        )
    )
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    flattened = flatten_strings(data)
    combined = "\n".join(flattened)

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            deny("Blocked destructive command. Use a safer non-destructive workflow.")

    lowered = combined.lower()
    for marker in GENERATED_PATH_MARKERS:
        if marker.lower() in lowered:
            deny("Blocked edits in generated directories. Edit source files instead.")


if __name__ == "__main__":
    main()
