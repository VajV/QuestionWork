from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    ".github/instructions/backend.instructions.md",
    ".github/instructions/alembic.instructions.md",
    ".github/instructions/frontend.instructions.md",
    ".github/instructions/api-contract.instructions.md",
    ".github/instructions/tests.instructions.md",
    ".github/agents/backend.agent.md",
    ".github/agents/frontend.agent.md",
    ".github/agents/migration.agent.md",
    ".github/agents/security-review.agent.md",
    ".github/prompts/create-backend-endpoint.prompt.md",
    ".github/prompts/create-alembic-migration.prompt.md",
    ".github/prompts/sync-api-contract.prompt.md",
    ".github/hooks/policy.json",
    ".vscode/mcp.json",
]


LEGACY_FILES = [
    ".github/copilot-agents.yml",
    ".github/copilot-skills.yml",
    ".github/copilot-tools.yml",
    ".github/mcp-config.json",
    ".mcp.json",
]


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Missing frontmatter: {path}")

    data: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"")
    return data


def ensure_exists() -> None:
    missing = [relative for relative in REQUIRED_FILES if not (ROOT / relative).exists()]
    if missing:
        raise SystemExit(f"Missing required customization files: {missing}")


def ensure_legacy_removed() -> None:
    present = [relative for relative in LEGACY_FILES if (ROOT / relative).exists()]
    if present:
        raise SystemExit(f"Legacy customization files should be removed: {present}")


def ensure_markdown_frontmatter() -> None:
    for relative in list((ROOT / ".github/instructions").glob("*.instructions.md")):
        frontmatter = parse_frontmatter(relative)
        if "description" not in frontmatter:
            raise SystemExit(f"Instruction missing description: {relative}")

    for relative in list((ROOT / ".github/agents").glob("*.agent.md")):
        frontmatter = parse_frontmatter(relative)
        if "description" not in frontmatter:
            raise SystemExit(f"Agent missing description: {relative}")

    for relative in list((ROOT / ".github/prompts").glob("*.prompt.md")):
        frontmatter = parse_frontmatter(relative)
        if "description" not in frontmatter:
            raise SystemExit(f"Prompt missing description: {relative}")


def ensure_skills_valid() -> None:
    for skill_file in (ROOT / ".github/skills").glob("*/SKILL.md"):
        frontmatter = parse_frontmatter(skill_file)
        skill_name = frontmatter.get("name")
        if skill_name != skill_file.parent.name:
            raise SystemExit(
                f"Skill name mismatch for {skill_file}: expected {skill_file.parent.name!r}, got {skill_name!r}"
            )


def ensure_json_valid() -> None:
    for relative in [ROOT / ".github/hooks/policy.json", ROOT / ".vscode/mcp.json"]:
        with relative.open("r", encoding="utf-8") as handle:
            json.load(handle)


def main() -> None:
    ensure_exists()
    ensure_legacy_removed()
    ensure_markdown_frontmatter()
    ensure_skills_valid()
    ensure_json_valid()
    print("Copilot customizations validated")


if __name__ == "__main__":
    main()