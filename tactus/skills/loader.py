"""
Agent Skills loader for the open Agent Skills standard.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import yaml


@dataclass
class SkillDefinition:
    name: str
    description: str
    path: str
    body: str
    metadata: dict


def discover_skills(paths: Iterable[str]) -> List[SkillDefinition]:
    skills: List[SkillDefinition] = []
    for root in paths:
        if not root:
            continue
        root_path = Path(root).expanduser().resolve()
        if root_path.is_file() and root_path.name.upper() == "SKILL.MD":
            skill = _load_skill_from_file(root_path)
            if skill:
                skills.append(skill)
            continue
        if not root_path.exists():
            continue
        if root_path.is_dir():
            for skill_file in root_path.rglob("SKILL.md"):
                skill = _load_skill_from_file(skill_file)
                if skill:
                    skills.append(skill)
    return skills


def render_skills_manifest(skills: List[SkillDefinition], include_body: bool = False) -> str:
    if not skills:
        return ""

    lines = ["<available_skills>"]
    for skill in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{skill.name}</name>")
        lines.append(f"    <description>{skill.description}</description>")
        lines.append(f"    <path>{skill.path}</path>")
        if include_body and skill.body:
            lines.append("    <instructions>")
            for line in skill.body.splitlines():
                lines.append(f"      {line}")
            lines.append("    </instructions>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def _load_skill_from_file(path: Path) -> Optional[SkillDefinition]:
    content = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(content)
    name = metadata.get("name") or path.parent.name
    description = metadata.get("description") or ""
    return SkillDefinition(
        name=str(name),
        description=str(description),
        path=str(path),
        body=body.strip(),
        metadata=metadata,
    )


def _split_frontmatter(content: str) -> tuple[dict, str]:
    lines = content.splitlines()
    if len(lines) >= 1 and lines[0].strip() == "---":
        end_idx = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                end_idx = idx
                break
        if end_idx is not None:
            frontmatter = "\n".join(lines[1:end_idx])
            body = "\n".join(lines[end_idx + 1 :])
            metadata = yaml.safe_load(frontmatter) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            return metadata, body

    return {}, content
