"""Atomic checkpoint.yaml updates for workers (headless runs block python -c and heredocs).

    study checkpoint <section> --scene Name [--say-draft built] [--layout passed|issues]
    study checkpoint <section> --last-error "text" | --clear-error
    study checkpoint <section> --propose-edit "Scene [NN]: proposed speech change"
    study checkpoint <section> --hold "Scene [NN]: why this line is a deliberate reading hold"
    study checkpoint <section> --freeze
    study checkpoint <section> --draft --model M --outcome "summary"

Only the named keys change; everything else is preserved. Writes go to a temp file, then rename.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

DRAFT_COMPLETED = ["notes", "storyboard", "script", "code", "draft_review"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, data: dict) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".checkpoint.", suffix=".yaml")
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    os.chmod(tmp, mode)  # mkstemp creates 0600; keep the checkpoint's own permissions
    os.replace(tmp, path)


PLAN_FILES = ('lesson.yaml', 'notes.md', 'script.md')


def plan_hashes(section: Path) -> dict:
    return {name: _sha(section / name) for name in PLAN_FILES}


def freeze_plan(section: Path, data: dict) -> None:
    """Publish validated plans, not animation or final approval."""
    from studio.review import parse_script
    if data.get('scene_progress') or data.get('state') in ('draft', 'ready', 'final'):
        raise ValueError('Cannot freeze over animation progress; handle revisions explicitly')
    spec = yaml.safe_load((section / 'lesson.yaml').read_text()) or {}
    scenes = spec.get('scenes') or []
    names = [s['name'] for s in scenes]
    blocks = parse_script((section / 'script.md').read_text())
    if (not names or len(set(names)) != len(names) or set(names) != set(blocks)
            or any(not str(s.get('storyboard') or '').strip() or s['storyboard'] == 'TODO' for s in scenes)
            or any(not blocks[n] or any(not text.strip() or text.strip() == 'TODO' for _, text in blocks[n]) for n in names)
            or not (section / 'notes.md').read_text().strip()):
        raise ValueError('Freeze needs notes, a storyboard and narrated blocks for every configured scene')
    data.update(state='frozen', completed=list(dict.fromkeys([*(data.get('completed') or []), *DRAFT_COMPLETED[:3]])),
                frozen_plan=plan_hashes(section), next_action='Animate once approved')


def update(section: Path, a) -> dict:
    path = section / "checkpoint.yaml"
    d = (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}
    if a.scene:
        sp = d.setdefault("scene_progress", {}) or {}
        d["scene_progress"] = sp
        entry = dict(sp.get(a.scene) or {})
        if a.say_draft:
            entry["say_draft"] = a.say_draft
        if a.layout:
            entry["layout_review"] = a.layout
        sp[a.scene] = entry
    if a.last_error is not None:
        d["last_error"] = a.last_error
    if a.clear_error:
        d["last_error"] = None
    if a.hold:
        d.setdefault("justified_static_holds", []).append(a.hold)
    if a.propose_edit:
        d.setdefault("proposed_speech_edits", []).append(a.propose_edit)
    if a.freeze:
        freeze_plan(section, d)
    if a.draft:
        d["state"] = "draft"
        done = list(d.get("completed") or [])
        d["completed"] = done + [c for c in DRAFT_COMPLETED if c not in done]
        fp = d.setdefault("input_fingerprint", {})
        if not isinstance(fp, dict):  # one combined hash string: keep it, start a per-file map
            fp = d["input_fingerprint"] = {"previous_combined_sha256": fp, "files": {}}
        files = fp.get("files") if isinstance(fp.get("files"), dict) else None
        target = files if files is not None else fp
        if (section / "scenes.py").exists():
            target["scenes.py"] = _sha(section / "scenes.py")
        if files is not None and "combined_sha256" in fp:
            fp["combined_sha256"] = hashlib.sha256(
                "\n".join(f"{k}:{files[k]}" for k in sorted(files)).encode()).hexdigest()
        d.setdefault("stage_runs", []).append({"stage": "animate+draft", "provider": a.provider,
                                               "model": a.model, "outcome": a.outcome})
        d.setdefault("roles", {})["animator"] = a.model
        d["next_action"] = "Coordinator: review say draft; narrate with the lesson engine after authorization"
    return d


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="study checkpoint", description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("section", type=Path)
    p.add_argument("--scene")
    p.add_argument("--say-draft", choices=["built", "failed"])
    p.add_argument("--layout", choices=["passed", "issues"])
    p.add_argument("--last-error")
    p.add_argument("--clear-error", action="store_true")
    p.add_argument("--propose-edit")
    p.add_argument("--hold", help='justified static reading hold: "Scene [NN]: reason"')
    transition = p.add_mutually_exclusive_group()
    transition.add_argument('--freeze', action='store_true', help='publish the validated plan to the animation queue')
    transition.add_argument("--draft", action="store_true", help="mark the section draft (after the consistency pass)")
    p.add_argument("--model", default="unknown")
    p.add_argument("--provider", default="anthropic")
    p.add_argument("--outcome", default="")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 2)
    if (a.say_draft or a.layout) and not a.scene:
        print("study checkpoint: --say-draft/--layout need --scene", file=sys.stderr)
        return 2
    if a.hold and not re.match(r"^\w+ \[\d{2}\]:", a.hold):
        print('study checkpoint: --hold must start with "Scene [NN]:"', file=sys.stderr)
        return 2
    section = a.section.resolve()
    if a.hold:
        lesson = section / "lesson.yaml"
        names = [s.get("name") for s in ((yaml.safe_load(lesson.read_text()) or {}).get("scenes") or [])] \
            if lesson.exists() else []
        if names and a.hold.split(" [", 1)[0] not in names:
            print(f'study checkpoint: --hold must name a scene from lesson.yaml ({", ".join(names)}), '
                  f'e.g. "{names[0]} [03]: reason"', file=sys.stderr)
            return 2
    try:
        data = update(section, a)
        _write(section / "checkpoint.yaml", data)
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f'study checkpoint: {exc}', file=sys.stderr)
        return 2
    print("checkpoint updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
