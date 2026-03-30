import json


def main() -> None:
    payload = {
        "systemMessage": (
            "QuestionWork customization policy loaded. Use .vscode/mcp.json as the MCP source of truth. "
            "Treat .next-dev, .venv, and audit artifact folders as generated outputs unless the task explicitly targets them."
        )
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
