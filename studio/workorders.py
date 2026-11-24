"""Scene work orders: animate a section as short, fresh, sequential workers (strategy D).

    study animate <section> [--group A,B ...] [--model M] [--effort high] [--budget 25]
                            [--dry-run] [--no-consistency] [--json]
    study animate <collection> [--follow] [--json]

One work order per scene (or per `workorder:` group in lesson.yaml / --group), then one
section-wide consistency pass. Each order is a compact bundle: that scene's frozen script and
beats, its traces, source-map rows and slide excerpts, the brief's notation, the current
scenes.py header (imports, constants, helper names), the rules and the exact commands. Workers
run headless one at a time (`hermes chat --query-file … -Q --ignore-rules --max-turns …`), so no
conversation history carries over and no coordinator turn is spent per scene. Progress lives
in checkpoint.yaml `scene_progress`; a rerun resumes at the first unfinished order.
"""
from __future__ import annotations

import argparse
import ast
import fcntl
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

import yaml

MODEL, PROVIDER = "claude-sonnet-5-5", "anthropic"
TOOLSETS = "terminal,file,vision"
QUOTA = re.compile(r"usage limit|rate[ _-]?limit|\b429\b|quota|exceeded your", re.I)
BRIEF_KEEP = re.compile(r"notation|colou?r|citation|approved decision|visual|style", re.I)
NOTES_SLICE = re.compile(r"corrections|issues|misconception", re.I)


# --- reading the section ----------------------------------------------------------------
def _load(path: Path) -> dict:
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def _sections(text: str, level: str = "## "):
    """[(heading line, body)] split at headings of exactly this level; preamble has heading ''."""
    out, head, body = [], "", []
    for line in text.splitlines():
        if line.startswith(level) and not line.startswith(level + "#"):
            out.append((head, "\n".join(body)))
            head, body = line, []
        else:
            body.append(line)
    out.append((head, "\n".join(body)))
    return out


def _mentions(text: str, name: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text) is not None


def _collection_root(section: Path) -> Path:
    for p in (section.parent.parent, section.parent, section):
        if (p / "collection.yaml").exists() or (p / "brief.md").exists():
            return p
    return section


def scene_names(section: Path) -> list[str]:
    return [s["name"] for s in _load(section / "lesson.yaml").get("scenes", [])]


def script_slice(script: str, scenes: list[str]) -> str:
    parts = _sections(script)
    pre = parts[0][1].strip()
    keep = [f"{h}\n{b.rstrip()}" for h, b in parts[1:] if h[3:].strip() in scenes]
    return "\n\n".join(([pre] if pre else []) + keep)


def _slides_of(text: str) -> set[str]:
    return set(re.findall(r"\bslides? (\d+)", text, re.I))


def notes_slice(notes: str, scenes: list[str], slides: set[str]) -> str:
    out = []
    for head, body in _sections(notes):
        if not head:
            continue
        title = head[3:]
        if re.search(r"source map", title, re.I):
            rows = [l for l in body.splitlines() if l.lstrip().startswith("|")]
            if rows:
                keep = rows[:2] + [r for r in rows[2:] if any(_mentions(r, s) for s in scenes)]
                out.append(f"{head}\n" + "\n".join(keep))
            continue
        subs = _sections(body, "### ")
        picked = [f"{h}\n{b.rstrip()}" for h, b in subs[1:]
                  if any(_mentions(h, s) for s in scenes)
                  or (h.lower().startswith("### slide") and _slides_of(h) & slides)]
        if picked:
            out.append(head + "\n" + "\n".join(picked))
            continue
        if re.search(r"slide excerpts", title, re.I):
            continue
        wide = bool(re.search(r"storyboard|transition", title, re.I) or NOTES_SLICE.search(title))
        lines, table_head = [], []
        body_lines = body.splitlines()
        for j, l in enumerate(body_lines):
            if not l.strip():
                continue
            is_row = l.lstrip().startswith("|")
            hit = (any(_mentions(l, s) for s in scenes) or re.search(r"\banimator\b", l, re.I)
                   or (wide and _slides_of(l) & slides))
            if is_row and not table_head and j + 1 < len(body_lines) and set(body_lines[j + 1].strip()) <= set("|-: "):
                table_head = [l, body_lines[j + 1]]
            if hit:
                if is_row and table_head and table_head[0] not in lines:
                    lines += table_head
                lines.append(l)
        if lines:
            out.append(head + "\n" + "\n".join(lines))
    return "\n\n".join(out)


def brief_slice(brief: str, slides: set[str]) -> str:
    out = []
    for head, body in _sections(brief):
        if not head:
            continue
        if re.search(r"known slide issues", head, re.I):
            rows = [l for l in body.splitlines() if l.lstrip().startswith("|")]
            hit = [r for r in rows[2:] if (m := re.match(r"\|\s*(\d+)", r)) and m.group(1) in slides
                   or _slides_of(r) & slides]
            if hit:
                out.append(f"{head}\n" + "\n".join(rows[:2] + hit))
        elif BRIEF_KEEP.search(head):
            out.append(f"{head}\n{body.strip()}")
    return "\n\n".join(out)


def scenes_header(section: Path, scenes: list[str]) -> tuple[str, list[str], list[str]]:
    """(imports + module constants source, local helper signatures, existing scene classes)."""
    path = section / "scenes.py"
    if not path.exists():
        return "", [], []
    src = path.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return f"# scenes.py does not parse: {e}", [], []
    lines, keep, helpers, existing = src.splitlines(), [], [], []
    known = set(scene_names(section))
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
            keep.append("\n".join(lines[n.lineno - 1:n.end_lineno]))
        elif isinstance(n, ast.ClassDef) and n.name in known:
            existing.append(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            helpers.append(lines[n.lineno - 1].strip().rstrip(":"))
    return "\n".join(keep), helpers, existing


def _locks(section: Path) -> tuple[str, str]:
    root = _collection_root(section)
    coll = _load(root / "collection.yaml")
    lock = coll.get("locks") or str(Path.home() / ".cache" / "study-locks" / root.name)
    sid = section.name
    return lock, shlex.join(['--lock', f'{lock}/cpu1', '--lock', f'{lock}/cpu2', '--owner', sid])


# --- rendering orders ---------------------------------------------------------------------
RULES = """\
## Rules (this order only)
- Copy each `[NN]` block VERBATIM into `self.voiceover(text=...)`, in order, including `[pause]`. Never edit
  script.md, notes.md, brief.md, other scenes, `studio/` or `source/`. Propose speech edits under
  `proposed_speech_edits` in checkpoint.yaml instead.
- Concept-first motion: animate only what teaches the spoken idea. Prefer staged reveals and static highlights
  (`focus`, `pulse`, `flow_flash`, `Timeline` arrows). Continuous motion (`packet_flight`, `Rotate`, updaters)
  only when the motion IS the concept, marked `# concept: <why>` on that line or the line above. If a beat asks
  for decoration (icons, dials, bubbles, wiggles), implement the idea with a labelled box/bar instead.
  Concept-first means no decoration, not fewer beats: every new idea in a block still gets its own visual
  change while it is spoken (reveal the label/value, flip the state, draw the arrow, highlight the part),
  synced with `<bookmark>`s or split plays. Fix every `static_speech` line that way. A line may stay still only
  as a deliberate reading hold, recorded with `"$STUDY" checkpoint "$S" --hold "Scene [NN]: reason"`.
- For independent content groups in the same beat (e.g. code/diagram and a state or annotation panel),
  keep a gutter and call `check_regions(code=listing, state=panel)` after positioning and geometry changes.
  Pass `required_lines=...` to `CodeListing` for the exact source lines this beat teaches. If they do not
  fit at readable size, show the listing alone first; remove it before introducing the next panel.
- Import cslib helpers; never redefine them: `P panel boxed card host pill mark text_at rich_text arrow bracket
  later appear cross_fade beat Timeline focus unfocus label SourceTag` and `self.wait_for(t, mark)`. Look up
  signatures with `"$STUDY" api cslib --grep NAME` (never dump the whole index). Reuse the module constants and
  helpers already in scenes.py (listed below); add new shared constants at the top of scenes.py.
- Edit scenes.py with small `patch` edits (or one `write_file` for a brand-new scene class). Do not write
  scratch generator scripts (`p1.py`, `fix*.py`) that rewrite scenes.py.
- Text ≥ 20, safe area ~13×7, source tag corner clear, change text with `cross_fade`, never `Transform`
  between strings. Labels exactly as the source-map rows below.
- This is a headless run: commands Hermes considers dangerous are refused (e.g. `python -c`, heredocs,
  `rm -rf`). Use the `study` commands, the `patch`/`write_file`/`read_file` tools, `ffmpeg`/`ffprobe`, and
  `"$STUDY" python <file.py>` for a saved script if you truly need one.
- Keep tool output short (`| tail -20`, `--grep`). Open contact sheets/frames with vision only for scenes the
  review flags, at most twice per scene.
"""


def render_order(section: Path, scenes: list[str], index: int, total: int, call_budget: int = 25,
                 continuation: bool = False, static_lines=None) -> str:
    section = Path(section)
    root = _collection_root(section)
    script = (section / "script.md").read_text() if (section / "script.md").exists() else ""
    sslice = script_slice(script, scenes)
    notes = (section / "notes.md").read_text() if (section / "notes.md").exists() else ""
    brief = (root / "brief.md").read_text() if (root / "brief.md").exists() else ""
    slides = _slides_of(sslice)
    for row in notes.splitlines():
        if row.lstrip().startswith("|") and any(_mentions(row, s) for s in scenes):
            m = re.match(r"\|\s*(\d+)\s*\|", row)
            if m:
                slides.add(m.group(1))
            slides |= _slides_of(row)
    header, helpers, existing = scenes_header(section, scenes)
    lock, lk = _locks(section)
    sid = section.name
    first = not existing and not header
    scene_args = " ".join(f"--scene {s}" for s in scenes)
    out = [f"# Animator work order {index}/{total} — section {sid}",
           f"Scenes: {', '.join(scenes)}",
           "",
           f"You are a fresh animator for ONLY the scene(s) above. Earlier scenes were done by other workers; "
           f"later ones will be. Budget: at most {call_budget} tool calls. By call {call_budget - 4} at the latest, "
           f"save scenes.py and update checkpoint.yaml, finished or not, then stop.",
           ""]
    if continuation:
        out += ["**Continuation:** the previous worker stopped before finishing. Read checkpoint.yaml "
                "(`scene_progress`, `last_error`) and the current scene class in scenes.py; continue from there, "
                "don't restart.", ""]
    if static_lines:
        out += ["**Still unfinished — mostly-still narration** (`narrate --check` static_speech): "
                + ", ".join(static_lines) + ". Give each new idea in these blocks its own visual change, or record "
                'a deliberate reading hold with `"$STUDY" checkpoint $S --hold "Scene [NN]: reason"`.', ""]
    if first:
        out += ["This is the first work order of the section: create scenes.py with imports, shared layout "
                "constants (lifeline x positions, colours per role, y rows) at the top, then your scene class. "
                "Later workers reuse those constants.", ""]
    out += [f"S={shlex.quote(str(section))}", 'STUDY="$HOME/.skills/manim-study-video/bin/study"', "",
            "## Steps",
            "1. Write the scene class(es) in `$S/scenes.py` (subclass `StudyScene`; source tag in every scene).",
            f'2. `"$STUDY" review "$S" --lint --layout --sheet {scene_args} {lk}` '
            "builds the say draft, records layout and makes contact sheets in one pass. No separate build.",
            f'3. `"$STUDY" narrate "$S" --check -q {scene_args}` (add `--engine say` only if the real-engine '
            "cache is empty). Fix errors and real warnings; at most two passes for the whole order, "
            "then review only changed scenes, then stop and record what is left.",
            "4. Record progress, per scene: " + "; ".join(
                f'`"$STUDY" checkpoint "$S" --scene {sc} --say-draft built --layout passed`' for sc in scenes)
            + " (use `--layout issues --last-error \"…\"` if something is unresolved; "
              "`--propose-edit \"Scene [NN]: …\"` for speech changes). Never edit checkpoint.yaml by hand.",
            "5. Final answer, ≤5 lines: scene durations, lint/layout/check summary, proposed speech edits.",
            "", RULES]
    if header or helpers or existing:
        out += ["## Current scenes.py (reuse; do not duplicate)", "```python", header, "```"]
        if helpers:
            out.append("Local helpers already defined: " + "; ".join(f"`{h}`" for h in helpers))
        if existing:
            out.append("Scene classes already written (do not edit unless your scene needs a shared constant): "
                       + ", ".join(existing))
        out.append("")
    out += ["## Script (frozen; your scenes only)", sslice, "",
            "## Notes for these scenes (traces, source map, slide text, corrections)", notes_slice(notes, scenes, slides), "",
            "## Brief (notation, citation, decisions, known issues for these slides)", brief_slice(brief, slides)]
    return "\n".join(out).rstrip() + "\n"


def render_consistency(section: Path, call_budget: int = 20) -> str:
    section = Path(section)
    root = _collection_root(section)
    brief = (root / "brief.md").read_text() if (root / "brief.md").exists() else ""
    _, lk = _locks(section)
    names = scene_names(section)
    return "\n".join([
        f"# Section consistency pass — {section.name}",
        "Scenes: ",
        "",
        f"All scenes ({', '.join(names)}) were animated by separate workers. Your job is consistency across "
        f"them, not new animation. Budget: at most {call_budget} tool calls.",
        "",
        f"S={shlex.quote(str(section))}", 'STUDY="$HOME/.skills/manim-study-video/bin/study"', "",
        "## Steps",
        f'1. `"$STUDY" review "$S" --lint --layout --sheet {lk}` (builds only stale draft clips; no separate build).',
        '2. `"$STUDY" narrate "$S" --check -q` (add `--engine say` if the real-engine cache is empty).',
        "3. Look at each scene's contact sheet once (build/review/<Scene>.png). Fix only cross-scene "
        "inconsistencies with small patches: the same role in a different colour or position, lifelines or hosts "
        "that jump between scenes, different label styles, a scene ending on clutter the next one does not expect, "
        "duplicated local helpers (move them to the top of scenes.py or replace with cslib), script_mismatch, "
        "errors. Rebuild only the scenes you changed with `--scene Name`.",
        '4. Mark the draft: `"$STUDY" checkpoint "$S" --draft --model <your model> --outcome "<one-line summary>"` '
        "(sets state draft, completed stages, scenes.py fingerprint, stage run, next action). Never edit "
        "checkpoint.yaml by hand.",
        "5. Final answer, ≤6 lines: draft duration, review/check summary, what you changed for consistency.",
        "", RULES,
        "## Brief (notation and decisions)", brief_slice(brief, set())]) + "\n"


def order_budget(base: int, n_scenes: int) -> int:
    """Tool-call budget for an order: base for one scene, +10 per extra scene."""
    return base + 10 * max(n_scenes - 1, 0)


AUTO_PAIR_ABOVE = 4  # sections with more scenes than this get two scenes per order by default


def plan(section: Path, groups: list[list[str]] | None = None, per_order: int | None = None) -> list[dict]:
    """Work orders. Explicit groups (--group / lesson.yaml `workorder:`) win; otherwise scenes are
    chunked `per_order` at a time (default: 2 when the section has > AUTO_PAIR_ABOVE scenes, else 1),
    because each order pays a fixed orientation/cache/build overhead."""
    section = Path(section)
    spec = _load(section / "lesson.yaml")
    names = [s["name"] for s in spec.get("scenes", [])]
    group_of: dict[str, str] = {}
    for g in groups or []:
        for s in g:
            if s not in names:
                raise ValueError(f"--group names unknown scene {s!r}; scenes: {', '.join(names)}")
            group_of[s] = "+".join(g)
    for s in spec.get("scenes", []):
        if s.get("workorder") and s["name"] not in group_of:
            group_of[s["name"]] = "wo:" + str(s["workorder"])
    if not group_of:
        k = per_order or (2 if len(names) > AUTO_PAIR_ABOVE else 1)
        for j, n in enumerate(names):
            group_of[n] = f"auto:{j // k}"
    orders, seen = [], {}
    for n in names:
        key = group_of.get(n, n)
        if key in seen:
            seen[key]["scenes"].append(n)
        else:
            seen[key] = {"kind": "scene", "scenes": [n]}
            orders.append(seen[key])
    for i, o in enumerate(orders, 1):
        o["name"] = f"{i:02d}-{'+'.join(o['scenes'])}"
    orders.append({"kind": "consistency", "scenes": [], "name": f"{len(orders) + 1:02d}-consistency"})
    return orders


# --- running ----------------------------------------------------------------------------
def _done(section: Path, order: dict) -> bool:
    ck = _load(section / "checkpoint.yaml")
    if order["kind"] == "consistency":
        return ck.get("state") in ("draft", "ready") and "draft_review" in (ck.get("completed") or [])
    prog = ck.get("scene_progress") or {}
    return all((prog.get(s) or {}).get("say_draft") == "built" and (prog.get(s) or {}).get("layout_review") == "passed"
               for s in order["scenes"])


def _usage(cmd) -> tuple[float | None, float | None]:
    try:
        data = json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, None
    s = w = None
    for win in data.get("windows", []):
        label = str(win.get("label", "")).lower()
        if "session" in label:
            s = float(win.get("used_percent", 0))
        elif "week" in label:
            w = float(win.get("used_percent", 0))
    return s, w


# --- telemetry (local, read-only; recorded right after each worker so rotated logs can't lose it) ------
TOKEN_COLS = ("api_call_count", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
              "reasoning_tokens")
API_CALL = re.compile(r"API call #\d+: .*? in=(\d+) out=(\d+)")


def _home(home=None) -> Path:
    import os
    return Path(home or os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def worker_record(session_id, home=None) -> dict:
    """{tokens, context, tools} for one Hermes session; None where the data is unavailable (never 0)."""
    import sqlite3
    if not session_id:
        return {"tokens": None, "context": None, "tools": None}
    h = _home(home)
    tokens = tools = context = None
    db = h / "state.db"
    if db.is_file():
        try:
            with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as c:
                row = c.execute(f"SELECT {', '.join(TOKEN_COLS)} FROM sessions WHERE id=?", (session_id,)).fetchone()
                if row:
                    tokens = dict(zip(TOKEN_COLS, row))
                calls = []
                for (tc,) in c.execute("SELECT tool_calls FROM messages WHERE session_id=? AND role='assistant' "
                                       "AND tool_calls IS NOT NULL ORDER BY timestamp", (session_id,)):
                    try:
                        calls += json.loads(tc)
                    except ValueError:
                        pass
                if row or calls:
                    tools = {"builds": 0, "reviews": 0, "narrate_checks": 0, "vision": 0, "patch": 0,
                             "write_file": 0, "read_file": 0, "terminal": 0, "total": len(calls)}
                    for c_ in calls:
                        f = c_.get("function") or {}
                        name = f.get("name")
                        if name == "vision_analyze":
                            tools["vision"] += 1
                        elif name in ("patch", "write_file", "read_file", "terminal"):
                            tools[name] += 1
                        if name == "terminal":
                            try:
                                cmd = json.loads(f.get("arguments") or "{}").get("command", "")
                            except ValueError:
                                cmd = ""
                            tools["builds"] += len(re.findall(r'study"? build\b', cmd, re.I))
                            tools["reviews"] += len(re.findall(r'study"? review\b', cmd, re.I))
                            tools["narrate_checks"] += len(re.findall(r'study"? narrate\b[^;|&]*--check', cmd, re.I))
        except sqlite3.Error:
            pass
    series = []
    for log in sorted((h / "logs").glob("agent.log*"), key=lambda p: p.stat().st_mtime):
        try:
            text = log.read_text(errors="replace")
        except OSError:
            continue
        tag = f"[{session_id}]"
        for line in text.splitlines():
            if tag in line and (m := API_CALL.search(line)):
                series.append(int(m.group(1)))
    if series:
        context = {"calls": len(series), "first": series[0], "peak": max(series), "sum": sum(series)}
    return {"tokens": tokens, "context": context, "tools": tools}


def review_record(section: Path):
    """Status, counts and issue codes of the section's latest review report, or None."""
    path = Path(section) / "build" / "review" / "report.json"
    try:
        r = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    codes: dict[str, int] = {}
    for i in r.get("issues", []):
        codes[i.get("code")] = codes.get(i.get("code"), 0) + 1
    return {"status": r.get("status"), "errors": r.get("errors"), "warnings": r.get("warnings"), "codes": codes}


def static_blocks(report: dict, scenes: list[str]) -> list[str]:
    """`narrate --check --json` lines (in scene order) → ["Scene [NN]", ...] flagged static_speech."""
    out, count = [], {}
    for line in report.get("lines", []):
        sc = line.get("scene")
        count[sc] = count.get(sc, 0) + 1
        if sc in scenes and line.get("static_speech"):
            out.append(f"{sc} [{count[sc]:02d}]")
    return out


def narrate_static_check(section: Path, scenes: list[str]) -> list[str]:
    """Unexplained static_speech blocks for these scenes, measured locally (no model tokens)."""
    import tempfile
    holds = [str(h) for h in (_load(section / "checkpoint.yaml").get("justified_static_holds") or [])]
    report = None
    for engine in ([], ["--engine", "say"]):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = Path(tmp.name)
        cmd = [sys.executable, "-P", "-m", "studio.build", "narrate", str(section), "--check", "--json", str(path),
               "-q", *engine] + [x for s in scenes for x in ("--scene", s)]
        subprocess.run(cmd, capture_output=True, text=True)
        try:
            report = json.loads(path.read_text())
        except (OSError, ValueError):
            report = None
        path.unlink(missing_ok=True)
        if report and not report.get("missing"):
            break
    if not report:
        return []
    return [b for b in static_blocks(report, scenes) if not any(h.startswith(b) for h in holds)]


def run(section: Path, model: str = MODEL, effort: str = "high", consistency_effort: str = "medium",
        call_budget: int = 25, groups=None, hermes: str = "hermes", usage_cmd=None, env=None,
        dry_run: bool = False, consistency: bool = True, per_order: int | None = None, session_limit: float = 80, week_limit: float = 92,
        static_check=narrate_static_check, hermes_home=None) -> dict:
    section = Path(section).resolve()
    orders = plan(section, groups, per_order)
    if not consistency:
        orders = orders[:-1]
    out_dir = section / "build" / "workorders"
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    usage_cmd = usage_cmd or [hermes, "usage", "--json"]
    total = len([o for o in orders if o["kind"] == "scene"])
    if dry_run:
        for i, o in enumerate(orders, 1):
            text = render_consistency(section) if o["kind"] == "consistency" else render_order(section, o["scenes"], i, total, order_budget(call_budget, len(o["scenes"])))
            (out_dir / f"{o['name']}.md").write_text(text)
        return {"status": "dry-run", "orders": [o["name"] for o in orders], "dir": str(out_dir)}
    runs = out_dir / "runs.jsonl"
    def finished(o):
        if not _done(section, o):
            return False, []
        if o["kind"] == "consistency" or static_check is None:
            return True, []
        left = static_check(section, o["scenes"])
        return not left, left

    for i, o in enumerate(orders, 1):
        ok, static_left = finished(o)
        if ok:
            continue
        for attempt in (1, 2):
            s_used, w_used = _usage(usage_cmd)
            if (s_used is not None and s_used >= session_limit) or (w_used is not None and w_used >= week_limit):
                return {"status": "paused", "order": o["name"], "reason": f"usage session {s_used}% week {w_used}%"}
            cons = o["kind"] == "consistency"
            text = (render_consistency(section, call_budget=max(call_budget - 5, 12)) if cons
                    else render_order(section, o["scenes"], i, total, order_budget(call_budget, len(o["scenes"])),
                                      continuation=attempt > 1,
                                      static_lines=static_left))
            qf = out_dir / f"{o['name']}{'' if attempt == 1 else '-a2'}.md"
            qf.write_text(text)
            budget = (max(call_budget - 5, 12) if cons else order_budget(call_budget, len(o["scenes"])))
            cmd = [hermes, "chat", "--query-file", str(qf), "-Q", "--provider", PROVIDER, "-m", model,
                   "--reasoning", consistency_effort if (cons or attempt > 1) else effort, "-t", TOOLSETS, "--ignore-rules",
                   "--max-turns", str(budget + 5), "--source", "tool", "--in", str(section)]
            started = time.time()
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
            output = proc.stdout + proc.stderr
            (out_dir / "logs" / f"{o['name']}-a{attempt}.log").write_text(output)
            sid = (re.findall(r"session_id:\s*(\S+)", output) or [None])[-1]
            quota = proc.returncode != 0 and QUOTA.search(output) is not None
            done, static_left = finished(o)
            outcome = "success" if done else ("quota" if quota else ("failed" if proc.returncode else
                                              ("static_speech" if static_left else "incomplete")))
            with runs.open("a") as f:
                f.write(json.dumps(dict(order=o["name"], attempt=attempt, section=section.name, kind=o["kind"],
                                        scenes=o["scenes"], session_id=sid, **worker_record(sid, hermes_home),
                                        review=review_record(section),
                                        model=model, effort=consistency_effort if (cons or attempt > 1) else effort,
                                        started_at=started, ended_at=time.time(), rc=proc.returncode,
                                        outcome=outcome, static_left=static_left)) + "\n")
            if done:
                break
            if quota:
                return {"status": "paused", "order": o["name"], "reason": "provider usage limit"}
        else:
            return {"status": "incomplete", "order": o["name"], "log": str(out_dir / "logs")}
    return {"status": "done", "orders": [o["name"] for o in orders], "runs": str(runs)}


def _queue_input(root: Path) -> dict:
    spec = _load(root / 'collection.yaml')
    sections = {}
    for row in spec.get('sections') or []:
        sid = row['id']
        path = (root / row.get('path', f'sections/{sid}')).resolve()
        after = row.get('animation_after', [])
        if sid in sections or path in {p for p, _ in sections.values()} or path == root or not path.is_relative_to(root):
            raise ValueError(f'Duplicate or out-of-collection section: {sid}')
        if not isinstance(after, list) or not all(isinstance(k, str) for k in after):
            raise ValueError(f'{sid}: animation_after must be a list of section IDs')
        sections[sid] = (path, after)
    if not sections:
        raise ValueError('Collection has no sections')
    pending = set(sections)
    while pending:
        ready = {sid for sid in pending if set(sections[sid][1]) <= sections.keys() - pending}
        if not ready:
            raise ValueError(f'Unknown or cyclic animation dependencies: {", ".join(sorted(pending))}')
        pending -= ready
    return sections


def run_collection(root: Path, animate, *, follow: bool = False, poll_s: float = 5) -> dict:
    """Drain approved frozen sections in one lane; completed checkpoints survive restarts."""
    from studio.checkpoint import PLAN_FILES, plan_hashes
    root = root.resolve()
    sections = _queue_input(root)
    out = root / 'build' / 'workorders'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'queue.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'busy'}
        journal = out / 'queue.jsonl'
        def emit(kind, **fields):
            with journal.open('a') as f:
                f.write(json.dumps(dict(kind=kind, at=time.time(), **fields)) + '\n')

        emit('resume')
        failures = {}
        while True:
            done = {sid for sid, (path, _) in sections.items() if _done(path, {'kind': 'consistency'})}
            waiting = {}
            progressed = False
            for sid, (path, after) in sections.items():
                if sid in done or sid in failures:
                    continue
                blocked = [dep for dep in after if dep not in done]
                checkpoint = _load(path / 'checkpoint.yaml')
                if blocked or checkpoint.get('state') != 'frozen':
                    waiting[sid] = blocked or ['not_frozen']
                    continue
                if not all((path / name).is_file() for name in PLAN_FILES):
                    failures[sid] = {'status': 'incomplete', 'reason': 'frozen section is missing planning inputs'}
                    continue
                if 'frozen_plan' in checkpoint and checkpoint['frozen_plan'] != plan_hashes(path):
                    failures[sid] = {'status': 'incomplete', 'reason': 'planning inputs changed since freeze'}
                    continue
                emit('section_start', section=sid)
                result = animate(path)
                status = result['status']
                emit('section_end', section=sid, status=status)
                if status == 'paused':
                    emit('pause', reason='quota', section=sid, detail=result.get('reason'))
                    return {**result, 'section': sid, 'incomplete': failures}
                if status == 'done' and _done(path, {'kind': 'consistency'}):
                    done.add(sid)
                    progressed = True
                else:
                    failures[sid] = result if status != 'done' else {'status': 'incomplete', 'reason': 'missing draft checkpoint'}
            if len(done) == len(sections):
                return {'status': 'done', 'sections': list(sections)}
            if waiting and progressed:
                continue  # a later-listed prerequisite may have unlocked an earlier section
            if not follow or not waiting or failures:
                return {'status': 'incomplete' if failures else 'waiting', 'waiting': waiting, 'incomplete': failures}
            time.sleep(poll_s)


def run_locked(section: Path, **options) -> dict:
    out = section / 'build' / 'workorders'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'section.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'busy', 'section': section.name}
        return run(section, **options)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="study animate", description="Animate a section or queue frozen collection sections.")
    p.add_argument("section", type=Path, metavar="section-or-collection")
    p.add_argument("--follow", action="store_true", help="collection only: wait for more sections to freeze; never auto-resume quota")
    p.add_argument("--group", action="append", default=[], help="comma-separated scenes sharing one work order")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--effort", default="high")
    p.add_argument("--consistency-effort", default="medium")
    p.add_argument("--budget", type=int, default=25, help="tool-call budget per work order")
    p.add_argument("--no-consistency", action="store_true")
    p.add_argument("--per-order", type=int, help="scenes per work order (default: 2 above 4 scenes, else 1)")
    p.add_argument("--dry-run", action="store_true", help="write the work orders, run nothing")
    p.add_argument("--json", action="store_true")
    p.add_argument("--session-limit", type=float, default=80, help="pause before an order at this 5-hour %% used")
    p.add_argument("--week-limit", type=float, default=92, help="pause before an order at this weekly %% used "
                   "(>100 disables; use when the usage API lags a reset)")
    a = p.parse_args(argv)
    groups = [[s.strip() for s in g.split(",") if s.strip()] for g in a.group]
    from studio.paths import lesson_dir
    folder = lesson_dir(str(a.section)).resolve()
    options = dict(model=a.model, effort=a.effort, consistency_effort=a.consistency_effort,
                   call_budget=a.budget, groups=groups, dry_run=a.dry_run, consistency=not a.no_consistency,
                   session_limit=a.session_limit, week_limit=a.week_limit, per_order=a.per_order)
    try:
        if (folder / 'collection.yaml').is_file():
            if a.group or a.no_consistency or a.dry_run:
                p.error('--group, --no-consistency and --dry-run are section-only')
            result = run_collection(folder, lambda section: run_locked(section, **options), follow=a.follow)
        else:
            if a.follow:
                p.error('--follow requires a collection')
            result = run_locked(folder, **options)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=1) if a.json else f"{result['status']}: {json.dumps({k: v for k, v in result.items() if k != 'status'})}")
    return {"done": 0, "dry-run": 0, "paused": 3, "waiting": 4, "busy": 5}.get(result["status"], 1)


if __name__ == "__main__":
    sys.exit(main())
