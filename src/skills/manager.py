"""
manager.py — Skill CRUD operations.

The agent can create, edit, patch, archive, and list skills.
This module is exposed as a tool (skill_manage) to the LLM.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.skills.loader import (
    SKILLS_DIR,
    ARCHIVE_DIR,
    VALID_NAME_RE,
    parse_frontmatter,
    discover_skills,
    get_skill_content,
    _load_usage,
    _save_usage,
)


def skill_manage(
    action: str,
    name: str = "",
    content: str = "",
    category: str = "general",
    old_string: str = "",
    new_string: str = "",
) -> dict:
    """
    Manage skills: create, edit, patch, delete, list, view.

    Actions:
        create — Create a new skill (requires name + content with frontmatter)
        edit   — Full rewrite of an existing skill
        patch  — Find-replace within a skill's content
        delete — Archive a skill (recoverable)
        list   — List all available skills
        view   — View a skill's full content
    """
    if action == "list":
        return _list_skills()
    elif action == "view":
        return _view_skill(name)
    elif action == "create":
        return _create_skill(name, content, category)
    elif action == "edit":
        return _edit_skill(name, content)
    elif action == "patch":
        return _patch_skill(name, old_string, new_string)
    elif action == "delete":
        return _archive_skill(name)
    else:
        return {"error": f"Unknown action: {action}. Use: create, edit, patch, delete, list, view"}


def _list_skills() -> dict:
    skills = discover_skills()
    return {
        "skills": [{"name": s["name"], "description": s["description"], "category": s["category"]} for s in skills],
        "count": len(skills),
    }


def _view_skill(name: str) -> dict:
    content = get_skill_content(name)
    if content is None:
        return {"error": f"Skill '{name}' not found."}
    return {"name": name, "content": content}


def _create_skill(name: str, content: str, category: str) -> dict:
    if not name:
        return {"error": "Skill name is required."}
    if not VALID_NAME_RE.match(name):
        return {"error": f"Invalid name '{name}'. Use lowercase, 3-64 chars, only [a-z0-9_-]."}
    if not content:
        return {"error": "Skill content is required (markdown with YAML frontmatter)."}

    # Validate frontmatter
    frontmatter, body = parse_frontmatter(content)
    if not frontmatter.get("name"):
        content = f"---\nname: {name}\ndescription: \"\"\n---\n\n{content}"
    if not body.strip():
        return {"error": "Skill must have body content after frontmatter."}

    # Check for collision
    skill_dir = SKILLS_DIR / category / name
    if skill_dir.exists():
        return {"error": f"Skill '{name}' already exists. Use 'edit' or 'patch' to modify."}

    # Write
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")

    # Track creation
    usage = _load_usage()
    usage[name] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "agent",
        "use_count": 0,
        "state": "active",
    }
    _save_usage(usage)

    logger.info(f"Skill created: {name} (category: {category})")
    return {"success": True, "message": f"Skill '{name}' created in {category}/.", "path": str(skill_file)}


def _edit_skill(name: str, content: str) -> dict:
    if not name or not content:
        return {"error": "Both name and content are required for edit."}

    # Find existing skill
    for skill_path in SKILLS_DIR.rglob("SKILL.md"):
        if ".archive" in str(skill_path):
            continue
        try:
            existing = skill_path.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(existing)
            if fm.get("name") == name or skill_path.parent.name == name:
                skill_path.write_text(content, encoding="utf-8")
                logger.info(f"Skill edited: {name}")
                return {"success": True, "message": f"Skill '{name}' updated."}
        except Exception:
            continue

    return {"error": f"Skill '{name}' not found."}


def _patch_skill(name: str, old_string: str, new_string: str) -> dict:
    if not old_string:
        return {"error": "old_string is required for patch."}

    for skill_path in SKILLS_DIR.rglob("SKILL.md"):
        if ".archive" in str(skill_path):
            continue
        try:
            content = skill_path.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            if fm.get("name") == name or skill_path.parent.name == name:
                if old_string not in content:
                    return {"error": f"old_string not found in skill '{name}'."}
                new_content = content.replace(old_string, new_string, 1)
                skill_path.write_text(new_content, encoding="utf-8")
                logger.info(f"Skill patched: {name}")
                return {"success": True, "message": f"Skill '{name}' patched."}
        except Exception:
            continue

    return {"error": f"Skill '{name}' not found."}


def _archive_skill(name: str) -> dict:
    for skill_path in SKILLS_DIR.rglob("SKILL.md"):
        if ".archive" in str(skill_path):
            continue
        try:
            content = skill_path.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            if fm.get("name") == name or skill_path.parent.name == name:
                skill_dir = skill_path.parent
                ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
                dest = ARCHIVE_DIR / skill_dir.name
                shutil.move(str(skill_dir), str(dest))
                logger.info(f"Skill archived: {name} -> {dest}")
                return {"success": True, "message": f"Skill '{name}' archived (recoverable)."}
        except Exception as e:
            return {"error": f"Archive failed: {e}"}

    return {"error": f"Skill '{name}' not found."}
