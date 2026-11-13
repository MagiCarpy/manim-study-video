"""Draft review: static lint, layout snapshots (reused from `study build --review`) and contact sheets.

No Manim or speech models are imported by lint/sheet. LayoutRecorder is imported lazily
by StudyScene only when STUDIO_LAYOUT is set. See references/review.md.

    study review <slug> [--lint] [--layout] [--sheet] [--frames N] [--width PX] [-q l|h] [--verbose]

Console output is a summary plus the top findings; the full report is build/review/report.md.
`--layout` reuses the snapshots of a `study build --review` draft when scenes.py, lesson.yaml,
lesson source and studio code are unchanged since that build; otherwise it rebuilds the draft.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
from weakref import WeakKeyDictionary

from studio.paths import SKILL_DIR, lesson_dir, rel

VERSION = 1
SAFE = (-6.5, -3.5, 6.5, 3.5)
SOURCE_REGION = (0.0, -4.0, 7.12, -3.0)
LATEX = {"MathTex", "Tex", "Matrix", "DecimalNumber", "Integer", "MathTable", "IntegerTable",
         "DecimalTable", "BulletedList", "Title", "BraceLabel", "SingleStringMathTex", "Variable"}
SHEET_COLS = 3  # sheet grid: at most this many frames across


def issue(code, message, **context):
    return {"severity": "error", "code": code, "message": message, **context}


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def layout_issues(boxes):
    """Text-only AABBs avoid false positives from a label contained in its panel.

    Distinct text objects are never exempted merely because one contains another.
    """
    found = []
    for i, a in enumerate(boxes):
        b = a["bbox"]
        if b[0] < SAFE[0] - .02 or b[1] < SAFE[1] - .02 or b[2] > SAFE[2] + .02 or b[3] > SAFE[3] + .02:
            found.append(issue("outside_safe_area", "Text extends outside 13 × 7 safe area", texts=[a["text"]], boxes=[b]))
        if a.get("font_size") is not None and a["font_size"] < 19.95:
            found.append(issue("small_font", "Rendered font size below 20", texts=[a["text"]], font_size=a["font_size"]))
        if not a["source"] and intersection(b, SOURCE_REGION) > .02:
            found.append(issue("source_region", "Text intrudes into reserved bottom-right source region", texts=[a["text"]], boxes=[b]))
        for other in boxes[:i]:
            area = intersection(b, other["bbox"])
            small = min((b[2]-b[0])*(b[3]-b[1]), (other["bbox"][2]-other["bbox"][0])*(other["bbox"][3]-other["bbox"][1]))
            if area > .02 and area / max(small, 1e-9) > .12:
                found.append(issue("text_overlap", "Text boxes overlap >12% of smaller box and >0.02 square units",
                                   texts=[other["text"], a["text"]], boxes=[other["bbox"], b]))
    return found


class LayoutRecorder:
    def __init__(self, path, scene):
        self.scene, self.narration = scene, None
        # One file per scene avoids interleaved writes from parallel render workers.
        p = Path(path).expanduser()
        self.path = p.with_name(f"{p.stem}.{type(scene).__name__}{p.suffix or '.jsonl'}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")
        self.elapsed = 0.0
        self.samples = 0
        self.text_overrides = WeakKeyDictionary()

    def record(self, animations=()):
        start = time.perf_counter()
        from manim import Text, MarkupText, Transform
        # Transform changes glyph geometry but Manim retains the original .text.
        def transformed(anim):
            if isinstance(anim, Transform):
                old, new = anim.mobject, anim.target_mobject
                if new is not None:
                    for a, b in zip(old.get_family(), new.get_family()):
                        if isinstance(a, (Text, MarkupText)) and isinstance(b, (Text, MarkupText)):
                            self.text_overrides[a] = dict(text=getattr(b, 'original_text', getattr(b, 'text', '')),
                                                          font_size=float(b.font_size), height=float(a.height),
                                                          source=bool(getattr(b, '_studio_source_tag', False)))
            for child in getattr(anim, 'animations', ()):
                transformed(child)
        for anim in animations:
            transformed(anim)
        boxes, seen = [], set()
        def visit(mob):
            if id(mob) in seen:
                return
            seen.add(id(mob))
            if isinstance(mob, (Text, MarkupText)):
                # Invisible glyphs (including completed FadeOut) don't contribute.
                glyphs = [g for g in mob.family_members_with_points()
                          if g.get_fill_opacity() > .01 or g.get_stroke_opacity() > .01]
                if not glyphs:
                    return
                import numpy as np
                points = np.concatenate([g.get_all_points() for g in glyphs])
                if not len(points):
                    return
                lo, hi = points.min(axis=0), points.max(axis=0)
                override = self.text_overrides.get(mob, {})
                text = override.get('text', getattr(mob, 'original_text', getattr(mob, 'text', '')))
                b = [float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])]
                source = override.get('source', False) or bool(getattr(mob, '_studio_source_tag', False)) or (
                    b[1] < -3 and bool(re.search(r'(?i)slide|added |correction|notes|\.pdf|\.md', text)))
                size = getattr(mob, 'font_size', None)
                if override and override['height'] > 0:
                    size = override['font_size'] * float(mob.height) / override['height']
                boxes.append(dict(text=text, bbox=b, font_size=float(size) if size is not None else None, source=source))
                return  # Don't count individual glyphs as labels.
            for child in mob.submobjects:
                visit(child)
        for mob in self.scene.mobjects:
            visit(mob)
        self.samples += 1
        row = dict(scene=type(self.scene).__name__, time=float(self.scene.renderer.time), narration=self.narration,
                   boxes=boxes, issues=layout_issues(boxes), sources=[b['text'] for b in boxes if b['source']])
        self.elapsed += time.perf_counter() - start
        row.update(recorder_s=self.elapsed, samples=self.samples)
        with self.path.open('a') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def static_lint(folder, spec):
    found = []
    path = folder / 'scenes.py'
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError) as e:
        return [issue('scenes_parse', str(e), file='scenes.py')]
    aliases = {a.asname or a.name: a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    def name(n):
        raw = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else ''
        return aliases.get(raw, raw)
    def literal(n):
        try:
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                return literal(n.left) + literal(n.right)
            return ast.literal_eval(n)
        except (ValueError, TypeError):
            return None
    known = pronounce_keys() | set((spec.get('pronounce') or {}) if isinstance(spec.get('pronounce'), dict) else ())
    unknown = {}  # all-caps word with no spoken form -> narration line numbers
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    for scene in spec['scenes']:
        cls = classes.get(scene['name'])
        if cls is None:
            found.append(issue('missing_scene', 'lesson.yaml scene missing from scenes.py', scene=scene['name']))
        elif not any(isinstance(n, ast.Call) and name(n.func) in {'source_tag', 'SourceTag', 'slide_excerpt'} for n in ast.walk(cls)):
            found.append(issue('missing_source_tag', 'Scene has no direct source_tag usage (check inherited/helpers manually)', scene=scene['name'], line=cls.lineno))
    braces = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
              and name(n.value.func) in {'Brace', 'BraceBetweenPoints', 'ArcBrace'}
              for t in n.targets if isinstance(t, ast.Name)}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        func = name(n.func)
        ctx = dict(file='scenes.py', line=n.lineno)
        if func in LATEX or (func in {'Axes', 'NumberLine'} and any(k.arg == 'include_numbers' and literal(k.value) is True for k in n.keywords)):
            found.append(issue('latex', f'{func} may invoke LaTeX', **ctx))
        if isinstance(n.func, ast.Attribute):
            recv = n.func.value
            on_brace = (isinstance(recv, ast.Name) and recv.id in braces) or (
                isinstance(recv, ast.Call) and name(recv.func) in {'Brace', 'BraceBetweenPoints', 'ArcBrace'})
            if func == 'get_tex' or (func == 'get_text' and on_brace):
                found.append(issue('latex', f'.{func}() builds Tex/MathTex; use a plain Brace plus '
                                   'cslib.label(...).next_to(brace, ...)', **ctx))
            elif func in {'add_numbers', 'add_coordinates'}:
                found.append(issue('latex', f'.{func}() builds LaTeX numbers; place cslib.label() text instead', **ctx))
        for kw in n.keywords:
            val = literal(kw.value)
            if (kw.arg == 'font_size' or (kw.arg == 'size' and func in {'label', 'source_tag'})) and isinstance(val, (int, float)) and val < 20:
                found.append(issue('small_font', f'{kw.arg}={val} below 20', **ctx))
        if func == 'voiceover':
            text = next((literal(k.value) for k in n.keywords if k.arg == 'text'), None)
            if text is None and n.args:
                text = literal(n.args[0])
            if not isinstance(text, str):
                found.append({**issue('dynamic_narration', 'Cannot statically inspect dynamic narration', **ctx), 'severity': 'warning'})
                continue
            clean = re.sub(r'<[^>]*>|\[\[.*?\]\]|\[[^\]]*\]', '', text)
            words = len(clean.split())
            sentences = len(re.findall(r'[.!?]+(?:\s|$)', clean))
            if words > 40 or sentences > 3:
                found.append(issue('long_voiceover', f'Voiceover has {words} words / {sentences} sentences', text=text, **ctx))
            if re.search(r'\bI\s+P\b', text):
                found.append(issue('spelled_ip', "Use IP with pronunciation rules rather than 'I P' in narration", text=text, **ctx))
            for word in acronyms(text):
                if word not in known:
                    unknown.setdefault(word, []).append(n.lineno)
    for word, lines in sorted(unknown.items()):
        found.append({**issue('unknown_acronym', f"{word} has no spoken form (voice will guess); add "
                              f"`pronounce: {{{word}: ...}}` to lesson.yaml, or tts.PRONOUNCE if it is common",
                              file='scenes.py', line=lines[0], count=len(lines)), 'severity': 'warning'})
    side = folder/'build' if (folder/'build'/'captions.srt').exists() else folder/'build'/'draft'
    for file in [side/'captions.srt', side/'transcript.md']:
        if not file.exists():
            found.append({**issue('missing_sidecar', 'Caption/transcript lint unavailable until build', file=str(file.relative_to(folder))), 'severity': 'warning'})
            continue
        for i, line in enumerate(file.read_text().splitlines(), 1):
            # Exclude generated transcript chapter timestamps and ordinary markdown links.
            clean = re.sub(r'^## \[[0-9:]+\]', '##', line) if file.suffix == '.md' else line
            clean = re.sub(r'\[[^\]]+\]\([^)]*\)', '', clean)
            if re.search(r'\[\[.*?\]\]|\[[A-Za-z][^\]\n]*\]|<bookmark\b', clean):
                found.append(issue('caption_tag', 'Narration tag leaked into captions/transcript', file=str(file.relative_to(folder)), line=i, text=line))
    return found + script_lint(folder)


# --- pronunciation ------------------------------------------------------------------------
_ACRONYM = re.compile(r'(?<![\w-])[A-Z][A-Z0-9]*[A-Z]s?(?![\w-])')  # 2+ capitals; letter+digit names are automatic
_SAID_AS_WRITTEN = {'OK', 'TV', 'AM', 'PM', 'US', 'UK', 'II', 'III', 'IV'}


def pronounce_keys():
    """tts.PRONOUNCE keys, read from source so lint loads no speech code."""
    tree = ast.parse((SKILL_DIR/'studio'/'tts.py').read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'PRONOUNCE' for t in n.targets):
            return {ast.literal_eval(k) for k in n.value.keys} | _SAID_AS_WRITTEN
    return set(_SAID_AS_WRITTEN)


def acronyms(text):
    """All-caps words in narration, ignoring bookmarks and [tags]."""
    clean = re.sub(r'<[^>]*>|\[\[.*?\]\]|\[[^\]]*\]', ' ', text)
    return _ACRONYM.findall(clean)


# --- script.md ----------------------------------------------------------------------------
def literal_value(node):
    try:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = literal_value(node.left), literal_value(node.right)
            return None if left is None or right is None else left + right
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def voiceover_text(call):
    """Normalized literal narration of a voiceover(...) call, or None when it is dynamic."""
    value = next((k.value for k in call.keywords if k.arg == 'text'), call.args[0] if call.args else None)
    text = literal_value(value) if value is not None else None
    return script_text(text) if isinstance(text, str) else None


def script_text(text):
    """Narration as compared with script.md: bookmark tags dropped, whitespace collapsed, [pause] kept."""
    return ' '.join(re.sub(r'<bookmark\b[^>]*>|</bookmark>', '', text).split())


def parse_script(text):
    """{scene: [[block number, text], ...]} from `## Scene` headings and `[NN] text` blocks.
    Multiline narration precedes an optional `beats:` suffix (including indented notes).
    That suffix is visual metadata through the next numbered block or heading."""
    scenes, scene, block = {}, None, None
    in_beats = False
    for line in text.splitlines():
        heading = re.fullmatch(r'## (\S.*?)\s*', line)
        numbered = re.match(r'\[(\d+)\]\s*(.*)', line)
        if heading:
            scene, block, in_beats = heading[1], None, False
            scenes.setdefault(scene, [])
        elif numbered and scene is not None:
            block, in_beats = [int(numbered[1]), numbered[2]], False
            scenes[scene].append(block)
        elif block is not None and re.match(r'\s*beats\s*:', line):
            in_beats = True
        elif block is not None and not in_beats and line.strip():
            block[1] += ' ' + line.strip()
    return scenes


def script_lint(folder):
    """Warn where script.md and the literal voiceover texts in scenes.py differ, scene by scene and in order."""
    script = folder / 'script.md'
    if not script.is_file():
        return []
    try:
        tree = ast.parse((folder / 'scenes.py').read_text())
    except (OSError, SyntaxError):
        return []  # static_lint already reports an unparseable scenes.py
    def warn(code, scene, message):
        return {**issue(code, message, scene=scene), 'severity': 'warning'}
    def short(text, at=0):
        """A 72-character window of text starting a little before index `at` (the first difference)."""
        start = max(0, at - 24)
        piece = text[start:start + 72]
        return json.dumps(('…' if start else '') + piece + ('…' if start + 72 < len(text) else ''), ensure_ascii=False)
    narration = {}  # scene -> normalized voiceover texts in source order; None when any text is dynamic
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        calls = sorted((n for n in ast.walk(cls) if isinstance(n, ast.Call)
                        and (n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, 'id', '')) == 'voiceover'),
                       key=lambda n: (n.lineno, n.col_offset))
        if calls:
            texts = [voiceover_text(c) for c in calls]
            narration[cls.name] = None if None in texts else texts
    scripted = parse_script(script.read_text(encoding='utf-8'))
    found = []
    for scene in dict.fromkeys([*narration, *scripted]):
        want_all = narration.get(scene, [])
        if want_all is None:
            continue  # dynamic narration: static_lint's dynamic_narration already flags it
        blocks = scripted.get(scene)
        if blocks is None:
            if want_all:
                found.append(warn('script_missing', scene, f'{len(want_all)} narration line(s) have no script.md section'))
            continue
        for i in range(max(len(want_all), len(blocks))):
            want = want_all[i] if i < len(want_all) else None
            have = blocks[i] if i < len(blocks) else None
            if have and want == script_text(have[1]):
                continue
            number = have[0] if have else i + 1
            if have is None:
                found.append(warn('script_missing', scene, f'block {number:02d} not in script.md: expected {short(want)}'))
            elif want is None:
                found.append(warn('script_mismatch', scene, f'block {number:02d} not in scenes.py: found {short(script_text(have[1]))}'))
            else:
                found_text = script_text(have[1])
                at = next((j for j, (a, b) in enumerate(zip(want, found_text)) if a != b), min(len(want), len(found_text)))
                found.append(warn('script_mismatch', scene, f'block {number:02d}: expected {short(want, at)} found {short(found_text, at)}'))
    return found


# --- layout snapshots -----------------------------------------------------------------
def review_dir(folder):
    return folder / 'build' / 'review'


def fingerprint(folder):
    """Hash of everything that can change a draft layout: scenes, lesson spec, lesson source text and studio code."""
    h = hashlib.sha256()
    files = [folder / 'scenes.py', folder / 'lesson.yaml']
    files += sorted(p for p in (folder / 'source').rglob('*.md') if p.is_file())
    files += sorted((SKILL_DIR / 'studio').rglob('*.py'))
    for p in files:
        if p.is_file():
            h.update(str(p).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def render_stamps(folder, names):
    from studio.build import scene_paths
    return [p.stat().st_mtime_ns if p.exists() else None for p in (scene_paths(folder, n, 'l')[0] for n in names)]


def layout_files(folder, names):
    return [review_dir(folder) / f'layout.{n}.jsonl' for n in names]


def read_layout_rows(folder, names):
    return [json.loads(line) for p in layout_files(folder, names) for line in p.read_text().splitlines() if line.strip()]


def record_layout(folder, spec, key, engine):
    """Called by `study build --review` after a full 480p draft: store the snapshots with the
    fingerprint taken before the build and the render stamps after it. Returns False if any scene left no snapshot."""
    names = [s['name'] for s in spec['scenes']]
    if not all(p.exists() and p.stat().st_size for p in layout_files(folder, names)):
        return False
    cache = review_dir(folder) / 'layout-cache.json'
    cache.write_text(json.dumps(dict(version=VERSION, fingerprint=key, engine=engine,
                                     renders=render_stamps(folder, names))))
    return True


def layout_reusable(folder, spec):
    """True when the recorded snapshots still match the lesson, source, studio code and 480p renders."""
    cache = review_dir(folder) / 'layout-cache.json'
    if not cache.exists():
        return False
    try:
        saved = json.loads(cache.read_text())
    except ValueError:
        return False
    names = [s['name'] for s in spec['scenes']]
    return (saved.get('version') == VERSION and saved.get('engine') == 'say'
            and saved.get('fingerprint') == fingerprint(folder)
            and saved.get('renders') == render_stamps(folder, names)
            and all(p.exists() and p.stat().st_size for p in layout_files(folder, names)))


def layout_review(folder, spec, out, locks, owner):
    names = [s['name'] for s in spec['scenes']]
    if layout_reusable(folder, spec):
        timing = dict(reused=True, build_s=0.0)
    else:
        cmd = [sys.executable, '-P', '-m', 'studio.build', str(folder), '--engine', 'say', '--jobs', '2',
               '--review', '--owner', owner]
        for lock in locks:
            cmd += ['--lock', lock]
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True)
        timing = dict(reused=False, build_s=time.perf_counter() - start)
        if result.returncode:
            tail = ' | '.join((result.stdout + result.stderr).strip().splitlines()[-3:])
            return [issue('layout_build', f'480p say build failed (exit {result.returncode}): {tail}')], [], timing
        if not layout_reusable(folder, spec):
            return [issue('layout_missing', 'No layout snapshots for one or more scenes; each scene must inherit StudyScene and play/wait')], [], timing
    rows = read_layout_rows(folder, names)
    found, dedup = [], set()
    for row in rows:
        for item in row['issues']:
            key = (row['scene'], item['code'], tuple(item.get('texts', [])))
            if key in dedup:
                continue
            dedup.add(key)
            found.append({**item, 'scene': row['scene'], 'time': row['time'], 'narration': row['narration']})
    overhead = sum(max((r.get('recorder_s', 0) for r in rows if r['scene'] == n), default=0) for n in names)
    timing.update(recorder_s=overhead, snapshots=len(rows))
    return found, rows, timing


# --- contact sheets -------------------------------------------------------------------
def contact_sheets(folder, spec, out, quality, rows, frames=6, width=1024):
    """One PNG per scene: `frames` evenly spaced stills (plus up to 2 source-label changes), 3 across,
    at most `width` px wide. Frames are scaled to the grid cell, so each sheet stays small."""
    from PIL import Image, ImageDraw, ImageFont
    from studio.build import scene_paths, ffprobe
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
    except OSError:
        font = ImageFont.load_default(size=14)
    cols = min(SHEET_COLS, frames)
    cell_w = width // cols
    cell_h = round(cell_w * 9 / 16)
    label = 22
    sheets, errors = [], []
    for scene in spec['scenes']:
        name = scene['name']
        video, _ = scene_paths(folder, name, quality)
        if not video.exists():
            errors.append(issue('missing_render', f'No {quality} render for contact sheet', scene=name))
            continue
        try:
            duration = ffprobe(video)['duration']
            times = {round(duration*(i+.5)/frames, 3) for i in range(frames)}
            previous, changes = None, []
            for row in sorted((r for r in rows if r['scene'] == name), key=lambda r: r['time']):
                sources = tuple(row['sources'])
                if sources != previous and sources:
                    changes.append(round(min(max(row['time'] + .1, 0), max(duration-.08, 0)), 3))
                previous = sources
            stride = max(1, math.ceil(len(changes) / 2))
            times = sorted(times | set(changes[::stride][:2]))
            grid_rows = math.ceil(len(times) / cols)
            sheet = Image.new('RGB', (cols * cell_w, grid_rows * (cell_h + label)), '#202020')
            draw = ImageDraw.Draw(sheet)
            for i, t in enumerate(times):
                data = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(video), '-frames:v', '1',
                                       '-vf', f'scale={cell_w}:{cell_h}', '-f', 'image2pipe', '-vcodec', 'png',
                                       '-threads', '1', '-'], check=True, capture_output=True).stdout
                x, y = (i % cols) * cell_w, (i // cols) * (cell_h + label)
                with Image.open(io.BytesIO(data)) as frame:
                    sheet.paste(frame.convert('RGB'), (x, y))
                draw.text((x + 6, y + cell_h + 3), f'{name}  {t:.2f}s', font=font, fill='white')
            path = out/f'{name}.png'
            sheet.save(path, optimize=True)
            sheets.append(str(path.relative_to(folder)))
        except (OSError, ValueError, subprocess.CalledProcessError) as e:
            errors.append(issue('sheet_failed', str(e), scene=name))
    return sheets, errors


# --- console -------------------------------------------------------------------------
def console_summary(report, issues, out, sheets, verbose, shown_default=8):
    errors, warnings = report['errors'], report['warnings']
    timing = report['timing']
    layout = ''
    if timing:
        layout = f"; layout {'reused' if timing.get('reused') else 'built'} ({timing.get('build_s', 0):.1f}s)"
    lines = [f"{report['status']}: {errors} errors, {warnings} warnings{layout} — {rel(out / 'report.md')}"]
    ranked = sorted(issues, key=lambda i: i['severity'] != 'error')
    shown = ranked if verbose else ranked[:shown_default]
    for item in shown:
        location = item.get('scene', item.get('file', 'lesson'))
        if 'time' in item:
            location += f" @ {item['time']:.2f}s"
        if 'line' in item:
            location += f":{item['line']}"
        text = f"  {item['severity']} {item['code']} · {location}: {item['message']}"
        if item.get('texts'):
            text += ' ' + json.dumps(item['texts'], ensure_ascii=False)
        lines.append(text if verbose else text[:200])
    if len(ranked) > len(shown):
        lines.append(f"  … {len(ranked) - len(shown)} more in {rel(out / 'report.md')}")
    if sheets:
        lines.append('sheets: ' + ', '.join(rel(out.parent.parent / s) for s in sheets))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='study review', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('slug')
    ap.add_argument('-q', '--quality', choices=['l', 'h'], default='l', help='existing render quality for sheets; layout always 480p say')
    for flag in ['lint', 'layout', 'sheet']:
        ap.add_argument('--'+flag, action='store_true')
    ap.add_argument('--frames', type=int, default=6, metavar='N', help='stills per scene in sheets (default 6)')
    ap.add_argument('--width', type=int, default=1024, metavar='PX', help='sheet width in px (default 1024)')
    ap.add_argument('--lessons-dir')
    ap.add_argument('--lock', action='append', help='repeatable CPU build slot (layout only)')
    ap.add_argument('--owner', default='review')
    ap.add_argument('--verbose', '-v', action='store_true', help='print every finding, not just the top ones')
    args = ap.parse_args(argv)
    if not any([args.lint, args.layout, args.sheet]):
        args.lint = args.sheet = True
    if args.frames < 1 or args.width < 64:
        ap.error('--frames must be >= 1 and --width >= 64')
    folder = lesson_dir(args.slug, args.lessons_dir)
    out = review_dir(folder)
    out.mkdir(parents=True, exist_ok=True)
    issues, rows, sheets, timing = [], [], [], {}
    started = time.perf_counter()
    try:
        import yaml
        spec = yaml.safe_load((folder/'lesson.yaml').read_text())
        if not spec.get('scenes'):
            raise ValueError('lesson.yaml has no scenes')
        names = [s['name'] for s in spec['scenes']]
        if args.layout:
            locks = args.lock or [str(Path.home()/'.cache/study-locks/skill-dev'/f'cpu{i}') for i in [1, 2]]
            found, rows, timing = layout_review(folder, spec, out, locks, args.owner)
            issues += found
        if args.lint:
            issues += static_lint(folder, spec)
        if args.sheet:
            # Draft timing is only used when it matches the current source and the 480p renders.
            if not rows and layout_reusable(folder, spec):
                rows = read_layout_rows(folder, names)
            sheets, errors = contact_sheets(folder, spec, out, args.quality, rows if args.quality == 'l' else [],
                                            args.frames, args.width)
            issues += errors
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as e:
        issues.append(issue('review_failed', str(e)))
    errors = sum(i['severity'] == 'error' for i in issues)
    report = dict(status='FAIL' if errors else 'PASS', errors=errors, warnings=len(issues)-errors, lesson=str(folder),
                  checks={k: getattr(args, k) for k in ['lint', 'layout', 'sheet']}, timing=timing,
                  elapsed_s=time.perf_counter()-started, issues=issues, sheets=sheets, version=VERSION)
    (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    md = [f"# {report['status']} — draft review\n\n{errors} errors; {report['warnings']} warnings. "
          f"Checks: {', '.join(k for k,v in report['checks'].items() if v)}.\n",
          '\nAutomated evidence only: passing checks do not establish visual or teaching correctness.\n',
          f'\nTiming: `{json.dumps(timing)}`; total {report["elapsed_s"]:.2f}s.\n']
    for item in issues:
        location = item.get('scene', item.get('file', 'lesson'))
        if 'time' in item:
            location += f" @ {item['time']:.2f}s"
        if 'line' in item:
            location += f":{item['line']}"
        md.append(f"\n- **{item['severity']} {item['code']}** · {location}: {item['message']}")
        if item.get('texts'):
            md.append(' — ' + json.dumps(item['texts'], ensure_ascii=False))
        if item.get('narration'):
            md.append('\n  Narration: ' + ' '.join(item['narration'].split()))
    for sheet in sheets:
        md.append(f'\n\n![{Path(sheet).stem}]({Path(sheet).name})\n')
    (out/'report.md').write_text(''.join(md)+'\n')
    print(console_summary(report, issues, out, sheets, args.verbose))
    return int(errors > 0)


if __name__ == '__main__':
    raise SystemExit(main())
