"""Proofread narration audio: transcribe each voiced line with Whisper and flag words the
voice misread (e.g. SDN heard as "SysBN", 31 heard as "thirteen").

The script and the transcript both go through tts.spoken_text() (so "R1", "R one" and
"R-1" compare equal), then are lowercased, split into words, and spelled letters are
normalized ("ess dee en" == "S D N"). Differing spans are reported; dropped or extra
small function words are ignored. Transcripts are cached per audio file in
build/proofread/cache.json, so only newly voiced lines are transcribed.

It cannot hear everything: stutters on spelled letters (e.g. "T T T L") usually come back
as the intended word. Treat a clean result as "nothing obvious", not a guarantee.

    study voice proofread <lesson> [--all] [--lock DIR]   # standalone (exit 1 if lines are flagged)
    study narrate <lesson>                                # runs it automatically after synthesis
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

from studio import tts

MODEL = "mlx-community/whisper-large-v3-turbo"
VERSION = 1  # bump when the transcription settings change (invalidates cached transcripts)
SHOWN = 8  # flagged lines printed to the console; the rest are in the report

_LETTERS = {"ay": "a", "bee": "b", "see": "c", "cee": "c", "dee": "d", "ee": "e", "ef": "f", "eff": "f",
            "gee": "g", "aitch": "h", "eye": "i", "jay": "j", "kay": "k", "el": "l", "ell": "l", "em": "m",
            "en": "n", "enn": "n", "pee": "p", "cue": "q", "queue": "q", "ar": "r", "are": "r", "ess": "s",
            "es": "s", "tee": "t", "vee": "v", "ex": "x", "zed": "z", "zee": "z"}
_MINOR = {"a", "an", "the", "and", "to", "of", "so", "it", "is", "that", "this", "in", "on", "uh", "um"}


def available() -> str | None:
    """None when proofreading can run, else the reason it cannot."""
    if importlib.util.find_spec("mlx_whisper") is None:
        return "mlx-whisper not installed (`study setup --proofread`, Apple Silicon only)"
    return None


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                      "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_UNITS["oh"] = 0
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i > 1}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}


def _digits(run: list[str]) -> str:
    """Number words -> digit string, splitting where a new number starts, so every way of saying a
    number matches Whisper's digits: "one hundred twenty-eight" / "one twenty-eight" -> "128",
    "fourteen eighty" -> "1480", "one zero zero" -> "100", "one oh five" -> "105"."""
    out, total, cur, last = [], 0, None, None  # last: kind of the previous word in this segment

    def flush():
        nonlocal total, cur, last
        if cur is not None or total:
            out.append(str(total + (cur or 0)))
        total, cur, last = 0, None, None
    for w in run:
        if w in _SCALES:
            if cur is None and not total:
                cur = 1
            if _SCALES[w] == 100:
                cur = (cur or 0) * 100
            else:
                total, cur = (total + (cur or 0)) * _SCALES[w], None
            last = "scale"
        elif w in _TENS:
            if last in ("unit", "tens") or (last == "teen"):
                flush()
            cur, last = (cur or 0) + _TENS[w], "tens"
        else:
            n = _UNITS[w]
            if last == "unit" or last == "teen" or (last == "tens" and n >= 10) or (last == "tens" and cur % 10):
                flush()
            if last == "tens" and n == 0:
                flush()
            cur, last = (cur or 0) + n, "teen" if n >= 10 else "unit"
            if n == 0 and cur == 0:
                out.append("0"); cur, last = None, None
    flush()
    return "".join(out)


def words(text: str, heard: bool = False) -> list[str]:
    """Comparable words: spoken form, lowercase, punctuation dropped, spelled letters as letters,
    and every number as digits (so "one twenty-eight", "128" and "1,28" all read "128")."""
    said = re.sub(r"(?<=\w)['’]s\b", "", tts.caption_text(text))  # possessives: "R1's" vs "R1s"
    if heard:
        said = re.sub(r"(?<=\d),(?=\d{3})", "", said)  # Whisper's 1,480
        said = re.sub(r"(?<=\d)\.(?=\d)", " dot ", said)  # 10.0.0.1 / 0.5, like the script's "dot"/"point"
        said = re.sub(r"\d+", lambda m: f" {' '.join(m.group(0)) if m.group(0)[0] == '0' and len(m.group(0)) > 1 else m.group(0)} ", said)  # 001 = zero zero one
    said = tts.spoken_text(said).lower().replace("-", " ")
    # Punctuation and "dot"/"point" end a number (and are not compared themselves).
    toks = [_LETTERS.get(w, w) for w in re.findall(r"[a-z0-9]+|[,.;:!?]", said.replace("'", "")) if w != "percent"]
    out, run = [], []
    for w in toks + [""]:
        if w in _UNITS or w in _TENS or (w in _SCALES and run):
            run.append(w)
            continue
        if run:
            out.append(_digits(run)); run = []
        if w and w not in ("dot", "point") and w[0].isalnum():
            out.append(w)
    return out


def _sound(ws: list[str]) -> str:
    """Rough sound key so spelling-only differences match ("cinak" ~ "sin ack", but "sdn" !~ "cdn")."""
    t = re.sub(r"c(?=[eiy])", "s", "".join(ws))
    for a, b in (("ck", "k"), ("c", "k"), ("ph", "f"), ("x", "ks"), ("y", "i"), ("z", "s")):
        t = t.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", t)


def compare(script: str, heard: str) -> list[dict]:
    """Spans where the transcript differs from the script (minor-word noise ignored)."""
    want, got = words(script), words(heard, heard=True)
    found = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, want, got, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        a, b = want[i1:i2], got[j1:j2]
        if set(a) | set(b) <= _MINOR or "".join(a) == "".join(b):  # "the" dropped; "trade off" vs "tradeoff"
            continue
        if a and b and difflib.SequenceMatcher(None, _sound(a), _sound(b)).ratio() >= 0.8:
            continue  # same sounds, different spelling: "ack"/"ak", "syn"/"sin", "x it"/"exit"
        found.append({"expected": " ".join(want[max(i1 - 2, 0):i2 + 2]),
                      "heard": " ".join(got[max(j1 - 2, 0):j2 + 2]), "words": " ".join(a) or "(nothing)",
                      "as": " ".join(b) or "(nothing)"})
    return found


def _cache_path(lesson_dir: Path) -> Path:
    return lesson_dir / "build" / "proofread" / "cache.json"


def transcribe(wavs: list[Path], lesson_dir: Path, recheck: bool = False) -> tuple[dict, int, float]:
    """{wav name: transcript}, number newly transcribed, seconds spent. Cached per audio file."""
    path = _cache_path(lesson_dir)
    cache = json.loads(path.read_text()) if path.exists() else {}
    out, new, t0 = {}, 0, time.time()
    for wav in wavs:
        key = f"{wav.name}|{MODEL}|v{VERSION}"
        if recheck or key not in cache:
            import mlx_whisper

            r = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODEL, language="en",
                                       condition_on_previous_text=False, temperature=0.0)
            cache[key] = r["text"].strip()
            new += 1
        out[wav.name] = cache[key]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return out, new, time.time() - t0


def proofread_lines(lesson_dir: Path, lines: list[dict], recheck: bool = False) -> dict:
    """Proofread narrate's line records ({scene, raw, text, wav}); writes build/proofread/report.md."""
    voiced = [(i, ln) for i, ln in enumerate(lines, 1) if ln.get("wav") and Path(ln["wav"]).exists()]
    heard, new, spent = transcribe([Path(ln["wav"]) for _, ln in voiced], lesson_dir, recheck)
    flagged = []
    for i, ln in voiced:
        said = heard[Path(ln["wav"]).name]
        spans = compare(ln.get("raw") or ln["text"], said)
        if spans:
            flagged.append({"line": i, "scene": ln["scene"], "text": tts.caption_text(ln.get("raw") or ln["text"]),
                            "heard": said, "spans": spans})
    report = lesson_dir / "build" / "proofread" / "report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    md = [f"# Proofread: {lesson_dir.name}", "",
          f"{len(voiced)} voiced lines, {len(flagged)} flagged ({MODEL}). Listen to each flagged line; "
          "fix with lesson.yaml `pronounce:` or by rewording, then re-run `study narrate`.", ""]
    for f in flagged:
        md += [f"## Line {f['line']} · {f['scene']}", "", f"- Script: {f['text']}", f"- Heard: {f['heard']}"]
        md += [f"- `{s['words']}` heard as `{s['as']}` (…{s['expected']}… / …{s['heard']}…)" for s in f["spans"]]
        md.append("")
    report.write_text("\n".join(md), encoding="utf-8")
    return {"lines": len(voiced), "new": new, "seconds": spent, "flagged": flagged, "report": str(report)}


def print_summary(result: dict, lesson_dir: Path) -> None:
    from studio.paths import rel

    n = len(result["flagged"])
    print(f"Proofread: {result['lines']} lines ({result['new']} transcribed, {result['seconds']:.1f}s), "
          f"{n} to listen to" + (":" if n else ""))
    for f in result["flagged"][:SHOWN]:
        pairs = "; ".join(f"{s['words']!r} heard as {s['as']!r}" for s in f["spans"][:3])
        print(f"  ? line {f['line']} {f['scene']}: {pairs}")
    if n > SHOWN:
        print(f"  … {n - SHOWN} more")
    if n:
        print(f"  details: {rel(Path(result['report']))}")


def main(argv=None) -> int:
    from studio import build

    ap = argparse.ArgumentParser(prog="study voice proofread", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="+", help="lesson folder names or paths")
    ap.add_argument("--lessons-dir", help="default: $STUDY_LESSONS_DIR or $STUDY_HOME/lessons (~/study-videos/lessons)")
    ap.add_argument("--engine", choices=list(tts.ENGINES), help="override lesson.yaml's voice engine")
    ap.add_argument("--recheck", action="store_true", help="transcribe again even when cached")
    ap.add_argument("--lock", action="append", metavar="DIR", help="hold this mkdir lock (e.g. the TTS lock)")
    ap.add_argument("--owner", help="lock owner label")
    args = ap.parse_args(argv)
    why = available()
    if why:
        print(f"proofread unavailable: {why}", file=sys.stderr)
        return 2
    lessons = [build.load_lesson(s, args.lessons_dir) for s in args.slug]
    lock = build.acquire_lock(args.lock, args.owner or lessons[0][0].name) if args.lock else None
    try:
        worst = 0
        for lesson_dir, spec in lessons:
            voice = tts.voice_config(spec, lesson_dir, args.engine)
            report = build.narration_check(lesson_dir, [s["name"] for s in spec["scenes"]], voice)
            if report is None:
                return 2
            missing = sum(ln["status"] == "miss" for ln in report["lines"])
            if missing:
                print(f"{lesson_dir.name}: {missing} line(s) not narrated yet (run `study narrate`); proofreading the rest")
            result = proofread_lines(lesson_dir, report["lines"], args.recheck)
            print_summary(result, lesson_dir)
            worst = max(worst, 1 if result["flagged"] else 0)
        return worst
    finally:
        build.release_lock(lock)


if __name__ == "__main__":
    sys.exit(main())
