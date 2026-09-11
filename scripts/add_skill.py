#!/usr/bin/env python3
"""Add a skill scaffold, create plugin config if needed, and generate manifests."""

import argparse
import json
from pathlib import Path
import re
import sys

from generate_manifests import CLI_FILES, ROOT, generate, render, sync_outputs


def add_skill(root, platform, plugin, skill, description):
    for label, value in (("platform", platform), ("plugin", plugin), ("skill", skill)):
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", value) or len(value) > 64:
            raise ValueError(f"{label} must be lower-case hyphenated words, at most 64 characters")
    if not description.strip() or len(description) > 1024:
        raise ValueError("description must contain 1–1024 characters")
    plugin_dir = root / "plugins" / platform / plugin
    if not plugin_dir.resolve().is_relative_to(root.resolve()):
        raise ValueError("plugin directory must stay inside the repository")
    config_path = plugin_dir / "plugin-config.json"
    skill_path = plugin_dir / "skills" / skill / "SKILL.md"
    if not skill_path.resolve().is_relative_to(root.resolve()) or not config_path.resolve().is_relative_to(root.resolve()):
        raise ValueError("skill and config paths must stay inside the repository")
    if skill_path.parent.exists():
        raise ValueError(f"skill directory already exists: {skill_path.parent}")
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        if any((plugin_dir / path).exists() for path in CLI_FILES.values()):
            raise ValueError("plugin has manifests but no plugin-config.json; migrate its settings first")
        marketplace = json.loads((root / "marketplace-metadata.json").read_text(encoding="utf-8"))
        config = {
            "$comment": "수정·저장 후 저장소 루트에서 python3 scripts/generate_manifests.py 실행. 검사: python3 scripts/generate_manifests.py --check",
            "name": plugin,
            "version": "0.1.0",
            "targets": ["claude", "codex", "gemini"],
            "dependencies": [],
            "description": description,
            "author": marketplace["owner"],
            "keywords": [platform],
            "claude": {"$schema": "https://json.schemastore.org/claude-code-plugin.json"},
            "codex": {"skills": "./skills/"},
            "gemini": {},
        }
    render(config)
    if config["name"] != plugin:
        raise ValueError("existing plugin-config name does not match the directory")

    created = []
    try:
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append(config_path)
        skill_path.parent.mkdir(parents=True)
        # JSON strings are valid YAML scalars: quotes/newlines in descriptions stay safe.
        skill_path.write_text(
            f"---\nname: {skill}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n"
            f"# {skill}\n\n## 지침\n\n"
            "이 스킬은 작성 중인 템플릿입니다. 구체적인 지침이 작성되기 전에는 작업을 실행하지 말고 미완성 상태임을 안내합니다.\n"
            "<!-- 배포 전 이 절을 실제 수행 절차·판단 기준·완료 조건으로 교체하세요. -->\n",
            encoding="utf-8",
        )
        created.append(skill_path)
        # Validate all plugins, including duplicate names, before updating any generated file.
        outputs = generate(root)
    except (OSError, ValueError, KeyError):
        for path in reversed(created):
            path.unlink()
        parent = skill_path.parent
        while parent != root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        raise
    sync_outputs(root, outputs)
    return skill_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, help="For example android, ios, flutter, shared")
    parser.add_argument("--plugin", required=True, help="Plugin name; create it if missing")
    parser.add_argument("--skill", required=True, help="New skill name")
    parser.add_argument("--description", required=True, help="When and why this skill is used")
    args = parser.parse_args()
    try:
        path = add_skill(ROOT, args.platform, args.plugin, args.skill, args.description)
    except (OSError, ValueError, KeyError) as error:
        print(f"Could not add skill: {error}", file=sys.stderr)
        return 1
    print(f"Created: {path.relative_to(ROOT)}")
    print("Plugin config and CLI manifests are ready. Edit SKILL.md before using or publishing the skill.")
    print("Existing plugin versions are unchanged; bump plugin-config.json version before release.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
