#!/usr/bin/env python3
"""Generate per-plugin manifests and a shared marketplace using only the stdlib."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
FIELDS = {"name", "version", "description", "author", "keywords"}
CLI_FILES = {
    "claude": ".claude-plugin/plugin.json",
    "codex": ".codex-plugin/plugin.json",
    "gemini": "gemini-extension.json",
}
SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def merge_settings(defaults, overrides):
    """Merge objects recursively; replace arrays/scalars; null removes a field."""
    result = deepcopy(defaults)
    for key, value in overrides.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            current = result.get(key)
            result[key] = merge_settings(current if isinstance(current, dict) else {}, value)
        else:
            result[key] = deepcopy(value)
    return result


def render(metadata):
    """Validate common fields and return deterministic, CLI-specific JSON text."""
    if not isinstance(metadata, dict) or not FIELDS <= set(metadata) or set(metadata) - FIELDS - set(CLI_FILES) - {"targets", "dependencies", "resources"}:
        raise ValueError("plugin-config requires common fields: " + ", ".join(sorted(FIELDS)) + "; optional sections: claude, codex, gemini")
    for key in ("name", "version", "description"):
        value = metadata[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", metadata["name"]):
        raise ValueError("name must use lower-case hyphenated words")
    if len(metadata["name"]) > 64:
        raise ValueError("name must not exceed 64 characters")
    if not SEMVER.fullmatch(metadata["version"]):
        raise ValueError("version must be semver, for example 0.1.0")
    author = metadata["author"]
    if not isinstance(author, dict) or not isinstance(author.get("name"), str) or not author["name"].strip():
        raise ValueError("author must be an object with a non-empty name")
    keywords = metadata["keywords"]
    if not isinstance(keywords, list) or any(not isinstance(word, str) or not word.strip() for word in keywords):
        raise ValueError("keywords must be an array of non-empty strings")
    common = {key: deepcopy(metadata[key]) for key in ("name", "version", "description", "author", "keywords")}
    manifests = {
        ".claude-plugin/plugin.json": deepcopy(common),
        ".codex-plugin/plugin.json": deepcopy(common),
        "gemini-extension.json": {key: metadata[key] for key in ("name", "version", "description")},
    }
    selected = targets(metadata)
    dependencies = dependency_map(metadata)
    for cli, path in CLI_FILES.items():
        settings = metadata.get(cli, {})
        if not isinstance(settings, dict):
            raise ValueError(f"{cli} settings must be an object")
        if {"name", "version"} & set(settings):
            raise ValueError(f"{cli}: name and version must be set in common fields only")
        if "dependencies" in settings:
            raise ValueError(f"{cli}: move dependencies to top-level dependencies (per CLI)")
        manifests[path] = merge_settings(manifests[path], settings)
        if cli == "claude" and dependencies[cli]:
            manifests[path]["dependencies"] = dependencies[cli]
        if cli not in selected:
            del manifests[path]
    return {
        path: json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        for path, value in manifests.items()
    }



def targets(config):
    value = config.get("targets", list(CLI_FILES))
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or x not in CLI_FILES for x in value) or len(set(value)) != len(value):
        raise ValueError("targets must be a non-empty unique array of claude, codex, gemini")
    return value


def dependency_map(config):
    value = config.get("dependencies", [])
    selected = targets(config)
    if isinstance(value, list):
        result = {cli: value if cli in selected else [] for cli in CLI_FILES}
    elif isinstance(value, dict) and set(value) == set(selected):
        result = {cli: value.get(cli, []) for cli in CLI_FILES}
    else:
        raise ValueError("dependencies must be an array or an object declaring every selected target")
    for cli, names in result.items():
        if not isinstance(names, list) or any(not isinstance(n, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", n) for n in names):
            raise ValueError(f"invalid dependencies for {cli}")
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate dependencies for {cli}")
    return result


def validate_components(directory, config):
    # Skills, agents and commands are distinct valid plugin components.
    patterns = ["skills/*/SKILL.md", "agents/**/*.md", "commands/**/*.md",
                "hooks/hooks.json", ".mcp.json", ".lsp.json", "SKILL.md"]
    resources = config.get("resources", [])
    if not isinstance(resources, list) or any(not isinstance(x, str) or not x for x in resources):
        raise ValueError("resources must be an array of plugin-relative file paths")
    found = any(p.is_file() for pattern in patterns for p in directory.glob(pattern))
    for relative in resources:
        path = directory / relative
        if Path(relative).is_absolute() or not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError(f"missing or invalid resource: {directory}/{relative}")
        found = True
    if not found:
        raise ValueError(f"plugin has no components; declare standalone scripts in resources: {directory}")


def dependency_order(name, cli, plugins):
    visiting, done, ordered = set(), set(), []
    def visit(current):
        if current in visiting:
            raise ValueError(f"dependency cycle for {cli}: {current}")
        if current in done:
            return
        visiting.add(current)
        for dependency in dependency_map(plugins[current][1])[cli]:
            if dependency not in plugins:
                raise ValueError(f"{current}: missing dependency {dependency} for {cli}")
            if cli not in targets(plugins[dependency][1]):
                raise ValueError(f"{current}: dependency {dependency} does not target {cli}")
            visit(dependency)
        visiting.remove(current)
        done.add(current)
        ordered.append(current)
    visit(name)
    return ordered


def generate(root):
    """Validate the complete catalog before returning any generated file."""
    marketplace = json.loads((root / "marketplace-metadata.json").read_text(encoding="utf-8"))
    if not isinstance(marketplace, dict) or set(marketplace) != {"name", "owner", "description"}:
        raise ValueError("marketplace metadata requires name, owner, description")
    if not isinstance(marketplace["name"], str) or not re.fullmatch(r"[a-z][a-z0-9-]*", marketplace["name"]):
        raise ValueError("invalid marketplace name")
    if not isinstance(marketplace["owner"], dict) or not isinstance(marketplace["owner"].get("name"), str) or not marketplace["owner"]["name"].strip():
        raise ValueError("marketplace owner.name is required")
    if not isinstance(marketplace["description"], str) or not marketplace["description"].strip():
        raise ValueError("marketplace description is required")
    directories = sorted(p for p in (root / "plugins").glob("*/*") if p.is_dir())
    if not directories:
        raise ValueError("no plugins found under plugins/<platform>/<plugin>/")
    generated, entries, plugins = {}, [], {}
    for directory in directories:
        path = directory / "plugin-config.json"
        if not path.is_file():
            raise ValueError(f"missing plugin-config.json: {directory}")
        metadata = json.loads(path.read_text(encoding="utf-8"))
        manifests = render(metadata)
        name = metadata["name"]
        if name != directory.name:
            raise ValueError(f"plugin name must match directory: {directory}")
        if name in plugins:
            raise ValueError(f"duplicate plugin name: {name}")
        validate_components(directory, metadata)
        relative = directory.relative_to(root).as_posix()
        plugins[name] = (relative, metadata)
        for filename, content in manifests.items():
            generated[f"{relative}/{filename}"] = content
        if set(targets(metadata)) & {"claude", "codex"}:
            entries.append({"name": name, "source": f"./{relative}", "description": metadata["description"]})
    catalog = {"name": marketplace["name"], "owner": marketplace["owner"],
               "metadata": {"description": marketplace["description"]}, "plugins": entries}
    generated[".claude-plugin/marketplace.json"] = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    # Keep dependency validation even though no installation guide is generated.
    for name, (_, config) in plugins.items():
        for cli in targets(config):
            dependency_order(name, cli, plugins)
    return generated


def sync_outputs(root, generated, check=False):
    """Update managed outputs, including removing manifests for disabled targets."""
    obsolete = []
    for config in (root / "plugins").glob("*/*/plugin-config.json"):
        for filename in CLI_FILES.values():
            path = config.parent / filename
            if path.exists() and path.relative_to(root).as_posix() not in generated:
                obsolete.append(path)
    changed = [relative for relative, content in generated.items()
               if not (root / relative).exists() or (root / relative).read_text(encoding="utf-8") != content]
    if not check:
        for relative in changed:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(generated[relative], encoding="utf-8")
        for path in obsolete:
            path.unlink()
    return changed + [str(path.relative_to(root)) for path in obsolete]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report stale files without writing")
    args = parser.parse_args()
    try:
        generated = generate(ROOT)
        stale = sync_outputs(ROOT, generated, check=args.check)
        if args.check and stale:
            print("Generated files are out of date:\n" + "\n".join(stale), file=sys.stderr)
            print("Run: python3 scripts/generate_manifests.py", file=sys.stderr)
            return 1
        print("Manifests are up to date." if args.check else f"Updated {len(stale)} manifest(s).")
        return 0
    except (OSError, ValueError) as error:
        print(f"Manifest generation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
