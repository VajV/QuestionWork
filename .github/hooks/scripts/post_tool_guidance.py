import json
import sys
from typing import Any


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


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    combined = "\n".join(flatten_strings(data)).lower()
    messages: list[str] = []

    if "backend/app/models/" in combined or "frontend/src/lib/api.ts" in combined or "frontend/src/types/" in combined:
        messages.append("API contract touched. Run the api-contract-sync workflow and validate backend plus frontend types.")

    if any(marker in combined for marker in ["wallet", "withdraw", "escrow", "quest", "dispute"]):
        messages.append("High-risk business flow touched. Run regression checks for quest, escrow, payout, and dispute paths.")

    if messages:
        print(json.dumps({"systemMessage": " ".join(messages)}))


if __name__ == "__main__":
    main()
