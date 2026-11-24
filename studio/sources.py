"""Timed sources.md from a section's notes.md source map, script.md and final captions.srt.

    study sources <section> [<section> ...]       one sources.md (+ sources.json) per section
    study sources <collection>                    every section listed in collection.yaml
    study sources <collection> --combined [--video combined.mp4]
                                                  one map for the assembled video, shifted by
                                                  the video's measured chapter starts

Times are measured, never estimated: script blocks are aligned to the caption words and each
source-map row spans the blocks its "Scene [01]–[03]" cell names. Any row that cannot be timed
fails the command and nothing is written. The credit/numbering lines come from `credits:` (a list of lines) in lesson.yaml or the
collection's collection.yaml; they must not contain TODO.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

MARKUP = re.compile(r"\[\[.*?\]\]|<bookmark[^>]*/>|\[pause\]")
WORD = re.compile(r"[a-z0-9]+")
DASHES = "–—-"
MAP_HEADING = re.compile(r"^##\s.*source map", re.I)
REF_HEADING = re.compile(r"^##\s.*(external references|references|added explanations|corrections)", re.I)


class SourcesError(Exception):
    pass


@dataclass
class Block:
    scene: str
    n: int
    text: str


def words(text: str) -> list[str]:
    return WORD.findall(MARKUP.sub(" ", text).lower().replace("’", "'").replace("'", ""))


def parse_script(text: str) -> list[Block]:
    """Numbered speech blocks under `## Scene` headings; a `beats:` note ends a block's speech."""
    blocks, scene, cur = [], None, None
    for line in text.splitlines():
        h = re.match(r"^##\s+(\w+)\s*$", line)
        b = re.match(r"^\[(\d+)\]\s*(.*)$", line)
        if h:
            scene, cur = h.group(1), None
        elif b and scene:
            cur = Block(scene, int(b.group(1)), b.group(2))
            blocks.append(cur)
        elif cur is not None:
            if line.strip().startswith("beats:") or not line.strip():
                cur = None
            else:
                cur.text += " " + line.strip()
    return blocks


def _seconds(stamp: str) -> float:
    h, m, rest = stamp.strip().split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def parse_srt(text: str) -> list[tuple[float, float, list[str]]]:
    cues = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        lines = chunk.splitlines()
        if len(lines) >= 2 and "-->" in lines[1]:
            a, b = lines[1].split("-->")
            cues.append((_seconds(a), _seconds(b), words(" ".join(lines[2:]))))
    return cues


def align(blocks: list[Block], cues) -> dict[tuple[str, int], tuple[float, float]]:
    """{(scene, n): (start, end)} by sequence-matching script words against caption words.

    Number formats ("65,535" vs "65535") and small TTS/caption differences only drop a few
    words; a block with too few matched words raises instead of being guessed.
    """
    script, owner = [], []
    for i, b in enumerate(blocks):
        ws = words(b.text)
        script += ws
        owner += [i] * len(ws)
    stream = [(w, a, z) for a, z, ws in cues for w in ws]
    matcher = difflib.SequenceMatcher(None, script, [w for w, _, _ in stream], autojunk=False)
    hits: dict[int, list[int]] = {}
    for m in matcher.get_matching_blocks():
        for k in range(m.size):
            hits.setdefault(owner[m.a + k], []).append(m.b + k)
    times = {}
    for i, b in enumerate(blocks):
        total = len(words(b.text))
        if not total:
            continue
        got = sorted(hits.get(i, []))
        if len(got) < max(1, round(0.6 * total)):
            raise SourcesError(f"cannot align {b.scene} [{b.n:02d}] to the captions "
                               f"({len(got)}/{total} words matched); are these the final captions?")
        times[(b.scene, b.n)] = (stream[got[0]][1], stream[got[-1]][2])
    return times


def beat_blocks(cell: str, known) -> list[tuple[str, int]]:
    """'Scene [01]–[03], [05]' / 'Scene (all)' → [(scene, n), ...] that exist in `known`."""
    m = re.match(r"^\s*`?(\w+)`?\s*(.*)$", cell)
    if not m:
        return []
    scene, rest = m.group(1), m.group(2)
    nums: list[int] = []
    for a, z in re.findall(rf"\[(\d+)\](?:\s*[{DASHES}]\s*\[(\d+)\])?", rest):
        nums += range(int(a), int(z or a) + 1)
    if not nums and re.search(r"\ball\b|\bwhole\b", rest, re.I):
        nums = sorted(n for s, n in known if s == scene)
    return [(scene, n) for n in nums if (scene, n) in known]


def _table(notes: str):
    lines = notes.splitlines()
    start = next((i for i, l in enumerate(lines) if MAP_HEADING.match(l)), None)
    if start is None:
        raise SourcesError("notes.md has no '## ... source map' section")
    header, rows = None, []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
        elif not set("".join(cells)) <= set("-: "):
            rows.append(cells)
    if header is None or not rows:
        raise SourcesError("source map table is empty")

    def col(*keys, exact=False):
        for i, h in enumerate(header):
            if (h in keys) if exact else any(k in h for k in keys):
                return i
        return None

    idx = dict(beat=col("beat", "scene"), locator=col("locator", "input"), label=col("label"),
               provenance=col("provenance", "status"), slide=col("slide", "slides", exact=True))
    missing = [k for k in ("beat", "locator", "label", "provenance") if idx[k] is None]
    if missing:
        raise SourcesError(f"source map header lacks {', '.join(missing)} column(s): {header}")
    return idx, rows


def _refs(notes: str) -> list[str]:
    out, grab = [], False
    for line in notes.splitlines():
        if REF_HEADING.match(line) and not MAP_HEADING.match(line):
            grab = True
            out.append(line.replace("## ", "### ", 1))
            continue
        if line.startswith("## "):
            grab = False
        if grab:
            out.append(line)
    out += [l for l in notes.splitlines() if l.startswith("External:") and l not in out]
    return out


def _load(path: Path) -> dict:
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def _collection_for(section: Path):
    for parent in [section.parent, section.parent.parent]:
        if (parent / "collection.yaml").exists():
            return parent
    return None


def _header(*specs) -> list[str]:
    for spec in specs:
        lines = (spec or {}).get("credits")
        if lines:
            lines = [lines] if isinstance(lines, str) else [str(l) for l in lines]
            if any("TODO" in l for l in lines):
                raise SourcesError("credits: still contains TODO; fill in the input credit line")
            return lines
    raise SourcesError("add `credits: [...]` lines (input file, author/course credit, numbering) "
                       "to lesson.yaml or collection.yaml")


def section_rows(section: Path, captions: Path | None = None):
    """[(beat, locator, label, provenance, start, end)] for one section, or SourcesError."""
    captions = captions or section / "build" / "captions.srt"
    for p in (section / "script.md", section / "notes.md", captions):
        if not p.exists():
            raise SourcesError(f"missing {p}")
    times = align(parse_script((section / "script.md").read_text()), parse_srt(captions.read_text()))
    notes = (section / "notes.md").read_text()
    idx, table = _table(notes)
    rows, untimed = [], []
    for cells in table:
        cells = cells + [""] * (1 + max(v for v in idx.values() if v is not None) - len(cells))
        beat = cells[idx["beat"]]
        loc = cells[idx["locator"]]
        if idx["slide"] is not None and cells[idx["slide"]] not in ("", "—", "-"):
            loc = f"slide {cells[idx['slide']]}" + ("" if loc in ("", "—", "-") else f" ({loc})")
        hit = beat_blocks(beat, times)
        if not hit:
            untimed.append(beat)
            continue
        rows.append((beat, loc, cells[idx["label"]], cells[idx["provenance"]],
                     min(times[h][0] for h in hit), max(times[h][1] for h in hit)))
    if untimed:
        raise SourcesError(f"{section.name}: untimed source-map rows (scene/block not in script): "
                           + "; ".join(untimed))
    return rows, _refs(notes), hashlib.sha256(captions.read_bytes()).hexdigest()


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:05.2f}"


def _hmmss(t: float) -> str:
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def section_sources(section: Path, captions: Path | None = None) -> dict:
    section = Path(section).resolve()
    coll = _collection_for(section)
    header = _header(_load(section / "lesson.yaml"), _load(coll / "collection.yaml") if coll else None)
    rows, refs, sha = section_rows(section, captions)
    out = [f"# Sources — {section.name}", "", *header,
           "Times are section-local (this section's MP4), measured from the final captions; format m:ss.ss.", "",
           "| beat | locator | on-screen label | provenance | section-local time |", "|---|---|---|---|---|"]
    out += [f"| {_cell(b)} | {_cell(l)} | {_cell(lab)} | {_cell(p)} | {_mmss(a)}–{_mmss(z)} |"
            for b, l, lab, p, a, z in rows]
    if refs:
        out += ["", "## References and corrections", "", *refs]
    build = section / "build"
    build.mkdir(exist_ok=True)
    (build / "sources.md").write_text("\n".join(out).rstrip() + "\n")
    (build / "sources.json").write_text(json.dumps(dict(
        section=section.name, captions_sha256=sha,
        rows=[dict(beat=b, locator=l, label=lab, provenance=p, start=a, end=z) for b, l, lab, p, a, z in rows]),
        indent=1, ensure_ascii=False) + "\n")
    return dict(section=section.name, rows=len(rows), untimed=[], path=str(build / "sources.md"))


def chapter_starts(video: Path) -> list[float]:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    return [float(c["start_time"]) for c in json.loads(out).get("chapters", [])]


def combined_sources(collection: Path, video: Path | None = None) -> dict:
    collection = Path(collection).resolve()
    spec = _load(collection / "collection.yaml")
    header = _header(spec)
    video = Path(video) if video else collection / "combined" / "build" / "combined.mp4"
    if not video.exists():
        raise SourcesError(f"missing combined video {video}")
    sections = spec.get("sections") or []
    starts = chapter_starts(video)
    if len(starts) != len(sections):
        raise SourcesError(f"{video.name} has {len(starts)} chapters but collection.yaml lists "
                           f"{len(sections)} sections; one chapter per section is required")
    out = [f"# Sources — {spec.get('title', collection.name)} (combined)", "", *header,
           "Times are positions in the combined video (h:mm:ss.ss): each section's measured map "
           "shifted by its chapter start.", ""]
    total = 0
    for sec, start in zip(sections, starts):
        rows, refs, _ = section_rows(collection / sec["path"])
        out += [f"## {sec.get('title', sec['id'])} ({sec['id']}) — starts {_hmmss(start)}", "",
                "| beat | locator | on-screen label | provenance | combined time |", "|---|---|---|---|---|"]
        out += [f"| {_cell(b)} | {_cell(l)} | {_cell(lab)} | {_cell(p)} | {_hmmss(a + start)}–{_hmmss(z + start)} |"
                for b, l, lab, p, a, z in rows]
        if refs:
            out += ["", *[r.replace("### ", "#### ", 1) for r in refs]]
        out.append("")
        total += len(rows)
    dest = collection / "combined" / "build" / "sources.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out).rstrip() + "\n")
    return dict(section="combined", rows=total, untimed=[], path=str(dest))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="study sources", description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("folders", nargs="+", type=Path, help="section folder(s), or a collection folder")
    p.add_argument("--combined", action="store_true", help="map for the assembled collection video")
    p.add_argument("--video", type=Path, help="combined video (default combined/build/combined.mp4)")
    p.add_argument("--captions", type=Path, help="captions for a single section (default build/captions.srt)")
    p.add_argument("--json", action="store_true", help="print a JSON result")
    args = p.parse_args(argv)
    results, ok = [], True
    for folder in args.folders:
        try:
            if args.combined:
                results.append(combined_sources(folder, args.video))
            elif (folder / "collection.yaml").exists() and not (folder / "notes.md").exists():
                for sec in _load(folder / "collection.yaml").get("sections") or []:
                    try:
                        results.append(section_sources(folder / sec["path"]))
                    except SourcesError as e:
                        ok = False
                        results.append(dict(section=sec["id"], error=str(e)))
            else:
                results.append(section_sources(folder, args.captions))
        except SourcesError as e:
            ok = False
            results.append(dict(section=folder.name, error=str(e)))
    if args.json:
        print(json.dumps(dict(ok=ok, results=results), indent=1))
    else:
        for r in results:
            print(f"{r['section']}: ERROR {r['error']}" if "error" in r else f"{r['section']}: {r['rows']} rows → {r['path']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
