from pathlib import Path

from tactus.skills.loader import discover_skills, render_skills_manifest


def test_discover_skills_parses_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill_one"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        """---\nname: Test Skill\ndescription: Test description\n---\n\nDo the thing.\n""",
        encoding="utf-8",
    )

    skills = discover_skills([str(tmp_path)])
    assert len(skills) == 1
    assert skills[0].name == "Test Skill"
    assert skills[0].description == "Test description"
    assert "Do the thing" in skills[0].body


def test_render_skills_manifest_includes_body(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill_two"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        """---\nname: Example\ndescription: Example description\n---\n\nStep 1\nStep 2\n""",
        encoding="utf-8",
    )

    skills = discover_skills([str(skill_dir)])
    manifest = render_skills_manifest(skills, include_body=True)

    assert "<name>Example</name>" in manifest
    assert "<description>Example description</description>" in manifest
    assert "Step 1" in manifest
