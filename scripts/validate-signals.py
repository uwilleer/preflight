#!/usr/bin/env -S uv run --quiet --with PyYAML python3
"""Validate skills/preflight/roles/signals/*.yaml.

Schema (per signals/README.md):
  group: <slug>
  matchers: [<str>, ...]
  augments_roles: [<role-name>, ...]   # must intersect roles/index.json
  checklist_intro: <str>
  checklist:
    - id: <slug>
      title: <str>
      rationale: <str>

Also asserts:
  - `group` is unique across files and matches the filename stem.
  - `augments_roles` references real roles from index.json.
  - `checklist[].id` is unique within a file.
  - Slash-wrapped matchers are valid regex (compiles).
  - Plain matchers are not single chars or trivially short (< 2 chars).
"""
import json
import re
import sys
from pathlib import Path

import yaml

SIGNALS_DIR = Path("skills/preflight/roles/signals")
INDEX_PATH = Path("skills/preflight/roles/index.json")

REQUIRED_TOP = {"group", "matchers", "augments_roles", "checklist_intro", "checklist"}
REQUIRED_ITEM = {"id", "title", "rationale"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not INDEX_PATH.is_file():
        fail(f"{INDEX_PATH} missing — run `make build-index` first")
    role_names = {r["name"] for r in json.loads(INDEX_PATH.read_text())}

    files = sorted(p for p in SIGNALS_DIR.glob("*.yaml"))
    if not files:
        fail(f"no signal YAMLs under {SIGNALS_DIR}")

    seen_groups: set[str] = set()
    for path in files:
        try:
            doc = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            fail(f"{path}: invalid YAML — {e}")
        if not isinstance(doc, dict):
            fail(f"{path}: top-level must be a mapping")

        missing = REQUIRED_TOP - doc.keys()
        if missing:
            fail(f"{path}: missing top-level keys: {sorted(missing)}")

        group = doc["group"]
        if not isinstance(group, str) or not group:
            fail(f"{path}: `group` must be a non-empty string")
        if group != path.stem:
            fail(f"{path}: `group` ({group!r}) must equal filename stem ({path.stem!r})")
        if group in seen_groups:
            fail(f"duplicate `group` slug across files: {group!r}")
        seen_groups.add(group)

        matchers = doc["matchers"]
        if not isinstance(matchers, list) or not matchers:
            fail(f"{path}: `matchers` must be a non-empty list")
        for m in matchers:
            if not isinstance(m, str) or not m:
                fail(f"{path}: matcher must be a non-empty string, got {m!r}")
            if m.startswith("/") and m.endswith("/") and len(m) >= 3:
                pattern = m[1:-1]
                try:
                    re.compile(pattern)
                except re.error as e:
                    fail(f"{path}: invalid regex matcher {m!r} — {e}")
            elif len(m) < 2:
                fail(f"{path}: substring matcher too short (<2 chars): {m!r}")

        augments = doc["augments_roles"]
        if not isinstance(augments, list) or not augments:
            fail(f"{path}: `augments_roles` must be a non-empty list")
        for r in augments:
            if r not in role_names:
                fail(f"{path}: `augments_roles` references unknown role {r!r} (not in {INDEX_PATH})")

        intro = doc["checklist_intro"]
        if not isinstance(intro, str) or not intro.strip():
            fail(f"{path}: `checklist_intro` must be a non-empty string")

        checklist = doc["checklist"]
        if not isinstance(checklist, list) or not checklist:
            fail(f"{path}: `checklist` must be a non-empty list")
        seen_ids: set[str] = set()
        for i, item in enumerate(checklist):
            if not isinstance(item, dict):
                fail(f"{path}: checklist[{i}] must be a mapping")
            missing = REQUIRED_ITEM - item.keys()
            if missing:
                fail(f"{path}: checklist[{i}] missing keys: {sorted(missing)}")
            iid = item["id"]
            if not isinstance(iid, str) or not iid:
                fail(f"{path}: checklist[{i}].id must be a non-empty string")
            if iid in seen_ids:
                fail(f"{path}: duplicate checklist id within file: {iid!r}")
            seen_ids.add(iid)
            for k in ("title", "rationale"):
                v = item[k]
                if not isinstance(v, str) or not v.strip():
                    fail(f"{path}: checklist[{i}].{k} must be a non-empty string")

    print(f"OK: {len(files)} signal YAML(s) validated ({sorted(seen_groups)})")


if __name__ == "__main__":
    main()
