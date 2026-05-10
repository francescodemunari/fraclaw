"""
loader.py — Discovers and loads skills from data/skills/.

Skills are markdown files with YAML frontmatter describing reusable
procedures the agent has learned or been taught.
"""

import re
import json
from pathlib import Path
from typing import Any

from loguru import logger

SKILLS_DIR = Path(__file__).parent.parent.parent / "data" / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

USAGE_FILE = SKILLS_DIR / ".usage.json"
ARCHIVE_DIR = SKILLS_DIR / ".archive"

VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown skill file."""
    if not content.startswith("---"):
        return {}, content

    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    yaml_content = content[3 : end_match.start() + 3]
    body = content[end_match.end() + 3 :]

    frontmatter = {}
    for line in yaml_content.strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    return frontmatter, body


def discover_skills() -> list[dict[str, Any]]:
    """Discover all available skills from the skills directory."""
    skills = []

    for skill_path in sorted(SKILLS_DIR.rglob("SKILL.md")):
        if ".archive" in str(skill_path):
            continue

        try:
            content = skill_path.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(content)

            skill_name = frontmatter.get("name", skill_path.parent.name)
            description = frontmatter.get("description", "")

            skills.append({
                "name": skill_name,
                "description": description,
                "path": str(skill_path),
                "category": skill_path.parent.parent.name if skill_path.parent.parent != SKILLS_DIR else "general",
            })
        except Exception as e:
            logger.warning(f"Error loading skill at {skill_path}: {e}")

    return skills


def get_skill_content(name: str) -> str | None:
    """Get the full content of a skill by name."""
    for skill_path in SKILLS_DIR.rglob("SKILL.md"):
        if ".archive" in str(skill_path):
            continue
        try:
            content = skill_path.read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(content)
            if frontmatter.get("name") == name or skill_path.parent.name == name:
                return content
        except Exception:
            continue
    return None


def build_skills_prompt() -> str:
    """Build a system prompt section listing available skills."""
    skills = discover_skills()
    if not skills:
        return ""

    by_category: dict[str, list[dict]] = {}
    for skill in skills:
        cat = skill["category"]
        by_category.setdefault(cat, []).append(skill)

    lines = ["\n## Available Skills"]
    for category, cat_skills in sorted(by_category.items()):
        lines.append(f"\n### {category}")
        for s in cat_skills:
            lines.append(f"- **{s['name']}**: {s['description']}")

    lines.append("\nUse `skill_view(name='skill-name')` to load a skill's full instructions.")
    return "\n".join(lines)


# ─── Usage Tracking ───────────────────────────────────────────────────────────

def _load_usage() -> dict:
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_usage(data: dict) -> None:
    USAGE_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def record_skill_use(name: str) -> None:
    """Record that a skill was used."""
    from datetime import datetime, timezone
    usage = _load_usage()
    if name not in usage:
        usage[name] = {"use_count": 0, "created_at": datetime.now(timezone.utc).isoformat()}
    usage[name]["use_count"] = usage[name].get("use_count", 0) + 1
    usage[name]["last_used_at"] = datetime.now(timezone.utc).isoformat()
    _save_usage(usage)


def get_skill_usage(name: str) -> dict:
    """Get usage stats for a skill."""
    usage = _load_usage()
    return usage.get(name, {})
