"""Render a lesson's scenes and assemble the final video.

    study build <slug|path> [--quality l|m|h|h60|k] [--scene Name ...] [--frames [N]] [--review]
                            [--engine say|fish] [--jobs N] [--cached-only] [--lessons-dir DIR] [--verbose]
    study narrate <slug|path> [--engine say|fish] [--scene Name ...] [--check] [--json PATH] [--verbose]

Default output is one line per scene plus a summary (video path, duration, problems, log dir);
--verbose restores Manim's output and the full per-file listing. --review (with -q l and
--engine say) also records the layout snapshots that `study review --layout` reuses.

Qualities: l=480p15 (draft), m=720p30, h=1080p30 (final), h60=1080p60, k=2160p60.

Reads <lessons>/<slug>/lesson.yaml (lessons dir: ~/study-videos/lessons by default), renders
each scene in scenes.py with Manim, then (when every scene has a render at this
quality) concatenates them into build/<slug>.mp4 and writes captions.srt,
transcript.md and chapters.txt next to it. Drafts (-q l, or an --engine that differs
from lesson.yaml's voice, e.g. `say`) go to build/draft/ instead, so a draft or
`study review --layout` never replaces the final video. --frames dumps N stills per rendered
scene into build/frames/ for visual review. --engine overrides lesson.yaml's
voice engine (e.g. fast `say` drafts, `fish` for the final). Fish narrates with
the lesson's voice preset (default `narrator`, see `study voice`).

Scenes render as parallel processes (--jobs N; default min(2, cpus/4) when every
narration line is already cached or the engine is `say`, else 1 so a TTS model isn't
loaded once per process). Logs: build/logs/<Scene>.<quality>.log.

`study narrate` runs each scene's construct() in one process without rendering
(play/wait only advance a virtual clock), synthesizes every uncached line into
the same voiceover cache the render uses (one model load), and prints a per-line
report: cache status, audio length, synth time, leading/trailing/longest
internal silence, and animation overrun past the narration. `--check` looks up
the cache only (writes nothing) and estimates missing lines.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from studio import tts
from studio.paths import SKILL_DIR, lesson_dir as find_lesson, rel
# -q option -> (manim flags, output dir). Final renders default to 1080p30 (~30% less CPU
# than 60 fps); `h60` keeps 1080p60 renders (and their 1080p60/ dirs) usable.
QUALITIES = {"l": (["-ql"], "480p15"), "m": (["-qm"], "720p30"), "h": (["-qh", "--fps", "30"], "1080p30"),
             "h60": (["-qh"], "1080p60"), "k": (["-qk"], "2160p60")}
QUALITY_DIRS = {q: d for q, (_, d) in QUALITIES.items()}


_CHILDREN: set = set()  # live render processes (terminated if the build is interrupted)
VERBOSE = False  # --verbose: also print routine progress (lock acquire/release, per-scene Manim output)


def note(msg: str) -> None:
    if VERBOSE:
        print(msg, flush=True)


def default_jobs() -> int:
    # Each Manim render uses ~2-3 cores (render + ffmpeg); keep headroom for the desktop.
    return max(1, min(2, (os.cpu_count() or 4) // 4))


def load_lesson(slug: str, lessons: str | None = None) -> tuple[Path, dict]:
    lesson_dir = find_lesson(slug, lessons)
    spec_path = lesson_dir / "lesson.yaml"
    if not spec_path.exists():
        sys.exit(f"missing {spec_path}")
    spec = yaml.safe_load(spec_path.read_text())
    scenes = spec.get("scenes") or []
    if not scenes:
        sys.exit("lesson.yaml has no scenes")
    for s in scenes:
        if "name" not in s:
            sys.exit(f"scene entry without 'name': {s}")
        s.setdefault("chapter", s["name"])
    return lesson_dir, spec


def ffprobe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    return {"duration": float(data["format"]["duration"]),
            "audio": any(s["codec_type"] == "audio" for s in data.get("streams", []))}


def scene_env(voice: dict, cached_only: bool = False) -> dict:
    env = dict(os.environ)
    # Scenes do `from studio... import ...`: resolve it from the skill dir, whatever the cwd.
    env["PYTHONPATH"] = str(SKILL_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONWARNINGS"] = "ignore::SyntaxWarning"
    env["STUDIO_TTS"] = json.dumps(voice)
    env["HF_HUB_OFFLINE"] = "1"  # local TTS models load from cache only
    if cached_only:
        env["STUDIO_TTS_CACHED_ONLY"] = "1"
    return env


def render_scene(lesson_dir: Path, name: str, quality: str, voice: dict, verbose: bool = False,
                 log: Path | None = None, echo: bool = True, private_cache: bool = False,
                 cached_only: bool = False) -> int:
    """Render one scene; returns the exit code. Output goes to `log` (and the terminal if `echo`)."""
    media = lesson_dir / "build" / "media"
    # -P: don't put the cwd on sys.path (a stray ./studio must not shadow the package).
    cmd = [sys.executable, "-P", "-m", "studio.manim_cli", "render", *QUALITIES[quality][0], "--disable_caching",
           "--media_dir", str(media), str(lesson_dir / "scenes.py"), name]
    if not verbose:
        cmd[5:5] = ["--verbosity", "ERROR", "--progress_bar", "none"]
    if private_cache:
        # Concurrent renders must not write the same Tex/Text svg cache files at once.
        cfg = lesson_dir / "build" / "tmp" / "cfg" / f"{name}.cfg"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(f"[CLI]\ntex_dir = {media / 'Tex' / '_jobs' / name}\n"
                       f"text_dir = {media / 'texts' / '_jobs' / name}\n")
        cmd[5:5] = ["--config_file", str(cfg)]
    if echo:
        print(f"\n=== rendering {name} ({QUALITY_DIRS[quality]}, voice: {voice['engine']}) ===", flush=True)
    env = scene_env(voice, cached_only)
    if log is None:
        log = log_path(lesson_dir, name, quality)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        proc = subprocess.Popen(cmd, env=env, cwd=lesson_dir, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        _CHILDREN.add(proc)
        try:
            for line in proc.stdout:
                f.write(line)
                if echo:
                    sys.stdout.write(line)
                    sys.stdout.flush()
            return proc.wait()
        finally:
            _CHILDREN.discard(proc)


def log_path(lesson_dir: Path, name: str, quality: str) -> Path:
    return lesson_dir / "build" / "logs" / f"{name}.{QUALITY_DIRS[quality]}.log"


def render_all(lesson_dir: Path, names: list[str], quality: str, voice: dict, jobs: int,
               verbose: bool = False, cached_only: bool = False) -> list[str]:
    """Render `names` with up to `jobs` concurrent processes; returns the failed scene names.
    After a failure no new scenes are started (running ones finish)."""
    failed, lock, stop = [], threading.Lock(), threading.Event()
    # Pre-create the shared narration cache dir: manim-voiceover's makedirs (no exist_ok)
    # races when two scene processes start on a fresh lesson.
    (lesson_dir / "build" / "media" / "voiceovers").mkdir(parents=True, exist_ok=True)

    def one(name: str) -> None:
        if stop.is_set():
            return
        log = log_path(lesson_dir, name, quality)
        t0 = time.time()
        if verbose and jobs > 1:
            with lock:
                print(f"[start] {name}", flush=True)
        code = render_scene(lesson_dir, name, quality, voice, verbose, log=log, echo=verbose and jobs == 1,
                            private_cache=jobs > 1, cached_only=cached_only)
        dt = time.time() - t0
        with lock:
            if code == 0:
                if verbose:
                    print(f"[done]  {name} ({dt:.1f}s)", flush=True)
                else:
                    print(f"  ok      {name:<24} {dt:5.1f}s", flush=True)
                return
            failed.append(name)
            stop.set()
            print(f"[FAILED] scene {name} (exit {code}, {dt:.1f}s); log: {rel(log)}", file=sys.stderr)
            if not (verbose and jobs == 1):  # serial verbose runs already streamed the output
                tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-(25 if verbose else 12):]
                print("\n".join("    " + l for l in tail), file=sys.stderr, flush=True)

    if jobs <= 1:
        for name in names:
            one(name)
    else:
        if verbose:
            print(f"Rendering {len(names)} scenes with {jobs} parallel jobs ({QUALITY_DIRS[quality]}, "
                  f"voice: {voice['engine']}); logs in {rel(lesson_dir / 'build' / 'logs')}/", flush=True)
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(one, names))
    return [n for n in names if n in failed]


def scene_paths(lesson_dir: Path, name: str, quality: str) -> tuple[Path, Path]:
    d = lesson_dir / "build" / "media" / "videos" / "scenes" / QUALITY_DIRS[quality]
    return d / f"{name}.mp4", d / f"{name}.srt"


# --- SRT helpers ------------------------------------------------------------------
_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _parse_ts(s: str) -> float:
    h, m, sec, ms = _TS.match(s.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms.ljust(3, "0")[:3]) / 1000


def _fmt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def read_srt(path: Path) -> list[tuple[float, float, str]]:
    if not path.exists():
        return []
    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()):
        lines = block.strip().splitlines()
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        a, b = lines[idx].split("-->")
        cues.append((_parse_ts(a), _parse_ts(b), " ".join(lines[idx + 1:]).strip()))
    return cues


def _clock(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


# --- assembly ---------------------------------------------------------------------
def normalize_clip(mp4: Path, tmp_dir: Path) -> Path:
    """Give every clip an audio track exactly as long as its video (silent
    scenes get silence, short narration gets padded) so concatenation can't drift."""
    out = tmp_dir / f"{mp4.stem}_norm.mp4"
    audio_in = [] if ffprobe(mp4)["audio"] else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    audio_map = "0:a:0" if not audio_in else "1:a:0"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), *audio_in,
                    "-map", "0:v:0", "-map", audio_map, "-af", "apad", "-shortest",
                    "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(out)],
                   check=True)
    return out


def _meta_escape(s: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", str(s))


def assemble(lesson_dir: Path, slug: str, spec: dict, quality: str, out_dir: Path | None = None) -> Path:
    """Concatenate scene renders into <out_dir>/<slug>.mp4 (+ captions/transcript/chapters).
    out_dir defaults to build/; drafts go to build/draft/ so they never replace the final."""
    build = out_dir or lesson_dir / "build"
    build.mkdir(parents=True, exist_ok=True)
    tmp = lesson_dir / "build" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    clips, offset, cues, chapters, transcript = [], 0.0, [], [], []
    for s in spec["scenes"]:
        mp4, srt = scene_paths(lesson_dir, s["name"], quality)
        clips.append(normalize_clip(mp4, tmp))
        dur = ffprobe(clips[-1])["duration"]
        scene_cues = read_srt(srt)
        cues += [(a + offset, b + offset, t) for a, b, t in scene_cues]
        chapters.append((offset, offset + dur, s["chapter"]))
        transcript.append((s["chapter"], " ".join(t for _, _, t in scene_cues)))
        offset += dur

    listing = tmp / "concat.txt"
    listing.write_text("".join("file '" + str(c.resolve()).replace("'", "'\\''") + "'\n" for c in clips))
    meta = tmp / "chapters.ffmeta"
    meta.write_text(";FFMETADATA1\ntitle=" + _meta_escape(spec.get("title", slug)) + "\n" + "".join(
        f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(a * 1000)}\nEND={int(b * 1000)}\ntitle={_meta_escape(t)}\n"
        for a, b, t in chapters))
    final = build / f"{slug}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-i", str(meta), "-map", "0", "-map_metadata", "1", "-map_chapters", "1",
                    "-c", "copy", "-movflags", "+faststart", str(final)],
                   check=True)

    (build / "captions.srt").write_text("".join(
        f"{i}\n{_fmt_ts(a)} --> {_fmt_ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1)), encoding="utf-8")
    (build / "chapters.txt").write_text("".join(f"{_clock(a)} {t}\n" for a, _, t in chapters), encoding="utf-8")
    md = [f"# {spec.get('title', slug)}\n"]
    for (a, _, title), (_, text) in zip(chapters, transcript):
        md.append(f"\n## [{_clock(a)}] {title}\n\n{text}\n")
    (build / "transcript.md").write_text("".join(md), encoding="utf-8")
    return final


def dump_frames(lesson_dir: Path, names: list[str], quality: str, n: int) -> list[Path]:
    out_dir = lesson_dir / "build" / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in names:
        mp4, _ = scene_paths(lesson_dir, name, quality)
        if not mp4.exists():
            continue
        for old in out_dir.glob(f"{name}_*.png"):
            old.unlink()
        dur = ffprobe(mp4)["duration"]
        for i in range(n):
            t = dur * (i + 0.5) / n
            png = out_dir / f"{name}_{i + 1:02d}_{t:05.1f}s.png"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(mp4),
                            "-frames:v", "1", str(png)], check=True)
            written.append(png)
    return written


# --- slot locks (parallel sections) --------------------------------------------------
def _owner_info(text: str) -> dict:
    """Parse `<owner> pid=N [host=H] [start=LSTART] since=ISO`; old files lack host/start."""
    pid, host, start = (re.search(p, text) for p in (r"\bpid=(\d+)", r"\bhost=(\S+)", r"\bstart=(.*?) since="))
    return {"pid": int(pid.group(1)) if pid else None, "host": host.group(1) if host else None,
            "start": start.group(1).strip() if start else None}


def _proc_start(pid: int) -> str | None:
    """Process start time as `ps` prints it (stable per process, so it detects pid reuse)."""
    out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return out or None


def _stale_reason(lock: Path, grace: float = 30.0) -> tuple[str, str] | None:
    """(owner text, reason) if `lock` was left by a dead or reused pid on this host; else None."""
    import socket
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return None  # released while we looked
    try:
        text = (lock / "owner").read_text().strip()
    except OSError:
        text = ""
    if not text:  # owner not written yet (or unreadable): only trust it after the grace period
        return ("", "owner file missing") if age >= grace else None
    info = _owner_info(text)
    if info["pid"] is None or info["host"] != socket.gethostname():
        return None  # unknown host (old format) or another machine: never reclaim
    try:
        os.kill(info["pid"], 0)
    except ProcessLookupError:
        return text, f"pid {info['pid']} dead"
    except PermissionError:
        pass  # alive, owned by another user
    if info["start"] and _proc_start(info["pid"]) not in (None, info["start"]):
        return text, f"pid {info['pid']} reused"
    return None


def _reclaim(lock: Path, text: str, reason: str) -> None:
    """Move the stale dir aside (rename is atomic, so one waiter wins), then delete it."""
    stale = lock.with_name(f"{lock.name}.stale-{os.getpid()}-{time.time_ns()}")
    try:
        os.rename(lock, stale)
    except OSError:
        return  # another waiter reclaimed it first
    try:
        now = (stale / "owner").read_text().strip()
    except OSError:
        now = ""
    if now != text:  # the lock was re-acquired between our check and the rename: put it back
        try:
            os.rename(stale, lock)
        except OSError:
            # Never delete a live holder's lock; leave it for manual inspection.
            print(f"[lock] WARNING: could not restore live lock {rel(lock)}; left at {stale}",
                  file=sys.stderr, flush=True)
        return
    shutil.rmtree(stale, ignore_errors=True)
    label = text.split(" pid=")[0] if text else "unknown"
    print(f"[lock] reclaimed stale {rel(lock)} (owner {label}, {reason})", flush=True)


def _try_mkdir(lock: Path) -> bool:
    try:
        lock.mkdir()
        return True
    except FileExistsError:
        stale = _stale_reason(lock)
        if stale is None:
            return False
        _reclaim(lock, *stale)
        try:
            lock.mkdir()
            return True
        except FileExistsError:
            return False


def acquire_lock(paths: list[str], owner: str, poll: float = 5.0, report_every: float = 60.0) -> Path:
    """Atomically take the first free mkdir lock among `paths` (waits until one is free)."""
    import socket
    locks = [Path(p).expanduser().resolve() for p in paths]
    last_report = None
    while True:
        for lock in locks:
            lock.parent.mkdir(parents=True, exist_ok=True)
            if _try_mkdir(lock):
                start = _proc_start(os.getpid())
                start_part = f" start={start}" if start else ""
                (lock / "owner").write_text(f"{owner} pid={os.getpid()} host={socket.gethostname()}{start_part} "
                                            f"since={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
                note(f"[lock] acquired {rel(lock)}")
                return lock
        if last_report is None or time.monotonic() - last_report >= report_every:
            held = ", ".join(f"{rel(l)} ({(l / 'owner').read_text().strip() if (l / 'owner').exists() else '?'})"
                             for l in locks)
            print(f"[lock] waiting for a free slot: {held}", flush=True)
            last_report = time.monotonic()
        time.sleep(poll)


def release_lock(lock: Path | None) -> None:
    if lock is not None and (lock / "owner").exists() and f"pid={os.getpid()} " in (lock / "owner").read_text():
        shutil.rmtree(lock, ignore_errors=True)
        note(f"[lock] released {rel(lock)}")


# --- narrate: synthesize narration without rendering ------------------------------------
def proofread_summary(proof: dict | None) -> dict | None:
    """Retain ASR seconds as well as counts; skipped checks stay unknown."""
    return {k: proof.get(k) for k in ("lines", "new", "flagged", "report", "seconds")} if proof else None


def silence_profile(wav: Path, thresh_db: float = -40.0, win: float = 0.02) -> dict:
    """Leading / trailing / longest internal silence (s) of a 16-bit WAV."""
    import numpy as np

    with wave.open(str(wav)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    hop = max(int(sr * win), 1)
    n = len(x) // hop
    if n == 0:
        return {"lead": 0.0, "tail": 0.0, "max_gap": 0.0}
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    voiced = np.flatnonzero(rms >= 10 ** (thresh_db / 20))
    if voiced.size == 0:
        return {"lead": n * win, "tail": 0.0, "max_gap": 0.0}
    gaps = np.diff(voiced) - 1
    return {"lead": voiced[0] * win, "tail": (n - 1 - voiced[-1]) * win,
            "max_gap": float(gaps.max() * win) if gaps.size else 0.0}


_SLNC_MS = re.compile(r"\[\[\s*slnc\s+(\d+)\s*\]\]")
_PAUSE = re.compile(r"(?<!\[)\[pause\](?!\])", re.I)
OVERRUN_WARN_S = 0.5  # animation running this far past its narration is reported
SILENCE_WARN_S = 1.0  # internal or edge silence this long is reported
STATIC_LINE_S = 8.0   # a narration line this long ...
STATIC_MOTION = 0.25  # ... with motion below this share of its audio, over 2+ sentences, is static_speech
_SENTENCE = re.compile(r"[.!?]+(?:\s|$)")


def sync_stats(ln: dict) -> None:
    """Annotate a narration line with on-screen motion during its speech (dry-run estimate)."""
    ln.setdefault("motion_s", 0.0)
    ln.setdefault("beats", 0)
    ln["sentences"] = max(len(_SENTENCE.findall(ln["text"])), 1)
    ln["motion_share"] = min(ln["motion_s"] / ln["audio_s"], 1.0) if ln["audio_s"] else 1.0
    ln["static_speech"] = (ln["audio_s"] > STATIC_LINE_S and ln["sentences"] >= 2
                           and ln["motion_share"] < STATIC_MOTION)


def narration_problems(ln: dict) -> list[str]:
    """Why a narration line needs attention (empty when it is fine)."""
    why = []
    if ln["status"] == "miss":
        why.append("missing (not cached; duration estimated)")
    if ln["overrun_s"] > OVERRUN_WARN_S:
        why.append(f"overrun {ln['overrun_s']:.1f}s")
    if ln.get("static_speech"):
        why.append(f"static_speech: {ln['audio_s']:.0f}s, {ln['sentences']} sentences, "
                   f"{ln['beats']} beat(s), motion {ln['motion_share']:.0%}; give each new idea its own beat")
    si = ln["silence"]
    if si and si["max_gap"] >= SILENCE_WARN_S:
        why.append(f"internal silence {si['max_gap']:.1f}s")
    if si and max(si["lead"], si["tail"]) >= SILENCE_WARN_S:
        why.append(f"edge silence {max(si['lead'], si['tail']):.1f}s")
    return why


def narrate(argv=None) -> int:
    """Narrate one or more lessons, retaining the model across lesson boundaries."""
    ap = argparse.ArgumentParser(prog="study narrate", description=(
        "Synthesize one or more lessons into their voiceover caches without rendering video "
        "(one process, one model load) and report per-line durations and silences."))
    ap.add_argument("slug", nargs="+", help="one or more lesson folder names or paths")
    ap.add_argument("--lessons-dir", help="default: $STUDY_LESSONS_DIR or $STUDY_HOME/lessons (~/study-videos/lessons)")
    ap.add_argument("--engine", choices=list(tts.ENGINES), help="override lesson.yaml's voice engine")
    ap.add_argument("--scene", action="append", help="only this scene (repeatable)")
    ap.add_argument("--check", action="store_true",
                    help="look up the cache only: synthesize and write nothing; estimate missing lines")
    ap.add_argument("--json", metavar="PATH", help="also write the report as JSON")
    ap.add_argument("--quiet", "-q", action="store_true", help="totals only (no per-scene lines or problems)")
    ap.add_argument("--verbose", "-v", action="store_true", help="also print every line and the per-line table")
    ap.add_argument("--no-proofread", action="store_true",
                    help="skip the Whisper proofread of voiced lines (on by default when installed)")
    ap.add_argument("--lock", action="append", metavar="DIR",
                    help="hold this mkdir lock (e.g. <collection>/locks/fish) while synthesizing")
    ap.add_argument("--owner", help="lock owner label (default: lesson folder name for one lesson; narrate for queues)")
    args = ap.parse_args(argv)
    global VERBOSE
    VERBOSE = args.verbose

    # Validate all paths before creating any caches. One lock spans the whole queue,
    # so other section workers cannot interleave model loads between lessons.
    lessons = [load_lesson(slug, args.lessons_dir) for slug in args.slug]
    lock = None
    reports = []
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        if args.lock and not args.check:
            lock = acquire_lock(args.lock, args.owner or (lessons[0][0].name if len(lessons) == 1 else "narrate"))
        result = 0
        for lesson_dir, spec in lessons:
            result = max(result, _narrate_lesson(args, lesson_dir, spec, reports))
        if args.json:
            # Keep the existing single-lesson JSON shape for downstream consumers.
            payload = reports[0] if len(reports) == 1 else {"lessons": reports}
            Path(args.json).write_text(json.dumps(payload, indent=2))
        return result
    finally:
        release_lock(lock)


def _narrate_lesson(args, lesson_dir: Path, spec: dict, reports: list) -> int:
    try:
        voice = tts.voice_config(spec, lesson_dir, args.engine)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(str(e))
    all_names = [s["name"] for s in spec["scenes"]]
    names = args.scene or all_names
    unknown = set(names) - set(all_names)
    if unknown:
        sys.exit(f"not in lesson.yaml: {', '.join(sorted(unknown))}")
    if not args.check:
        status = tts.engine_status()[voice["engine"]]
        if not status.startswith("ok"):
            sys.exit(f"voice engine {voice['engine']}: {status}  (or pass --engine say)")

    t_wall = time.time()
    sys.dont_write_bytecode = True  # leave no __pycache__ in the lesson
    os.environ.update({k: v for k, v in scene_env(voice).items() if k in ("STUDIO_TTS", "HF_HUB_OFFLINE")})
    os.environ.pop("STUDIO_TTS_CACHED_ONLY", None)
    from manim import config

    from studio.base import DryRun, StudyScene

    cache_dir = lesson_dir / "build" / "media" / "voiceovers"
    scratch_dir = tempfile.TemporaryDirectory(prefix="study-narrate-")  # removed in finally, even on errors
    scratch = Path(scratch_dir.name)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # run the finally blocks on kill
    try:
        # Mobjects built by construct() (Text/Tex svgs) go to a scratch media dir; audio to the real cache.
        config.media_dir = str(scratch)
        config.quality = "low_quality"
        config.disable_caching = True
        if not cache_dir.exists():
            if args.check:
                cache_dir = scratch / "voiceovers"
            else:
                cache_dir.mkdir(parents=True)
        service = tts.make_service({**voice, "cache_dir": str(cache_dir)})
        load = {"s": 0.0}

        def on_line(line: dict) -> None:
            if args.verbose:
                mark = {"hit": "hit  ", "synth": "SYNTH", "miss": "MISS "}[line["status"]]
                extra = f" synth {line['synth_s']:.1f}s" if line["status"] == "synth" else ""
                print(f"  [{mark}] {line['scene']:<22} {line['audio_s']:5.1f}s{extra}  {line['text'][:70]!r}", flush=True)

        dry = DryRun(service, check=args.check, on_line=on_line)
        if hasattr(service, "preload") and not args.check:
            orig, loaded = dry.voiceover, []

            def voiceover_with_load(scene, text):  # load the model once, on the first miss; time it separately
                if not loaded and service.lookup(" ".join(text.split())) is None:
                    load["s"] = service.preload()
                    loaded.append(True)
                return orig(scene, text)
            dry.voiceover = voiceover_with_load

        errors, scene_len = {}, {}
        old_cwd, old_path = os.getcwd(), list(sys.path)
        StudyScene.dry_run = dry
        print(f"Narration for {lesson_dir.name} ({voice['engine']}{', check only' if args.check else ''}):", flush=True)
        try:
            os.chdir(lesson_dir)  # same cwd as a render
            sys.path.insert(0, str(lesson_dir))
            mod_spec = importlib.util.spec_from_file_location("scenes", lesson_dir / "scenes.py")
            mod = importlib.util.module_from_spec(mod_spec)
            sys.modules["scenes"] = mod
            mod_spec.loader.exec_module(mod)
            for name in names:
                dry.scene_name = name
                try:
                    cls = getattr(mod, name)
                    if not (isinstance(cls, type) and issubclass(cls, StudyScene)):
                        raise TypeError(f"{name} is not a StudyScene subclass (narrate needs StudyScene)")
                    scene = cls()
                    scene.setup()
                    scene.construct()
                    scene_len[name] = scene._dry_t
                except Exception as e:  # report and continue with the other scenes
                    errors[name] = f"{type(e).__name__}: {e}"
                    print(f"  [ERROR] {name}: {errors[name]}", file=sys.stderr)
                    traceback.print_exc(limit=-3, file=sys.stderr)
        finally:
            StudyScene.dry_run = None
            os.chdir(old_cwd)
            sys.path[:] = old_path
    finally:
        scratch_dir.cleanup()

    # per-line timing report
    lines, prev_end = dry.lines, {}
    for ln in lines:
        ln["slnc_ms"] = sum(int(m) for m in _SLNC_MS.findall(ln["raw"]))
        ln["pauses"] = len(_PAUSE.findall(ln["raw"]))
        ln["block_end"] = ln.get("block_end", ln["start"] + ln["audio_s"])
        ln["overrun_s"] = max(ln["block_end"] - ln["start"] - ln["audio_s"], 0.0)
        ln["gap_before_s"] = ln["start"] - prev_end.get(ln["scene"], 0.0)
        prev_end[ln["scene"]] = ln["block_end"]
        ln["silence"] = silence_profile(Path(ln["wav"])) if ln["wav"] else None
        sync_stats(ln)
    hits = sum(ln["status"] == "hit" for ln in lines)
    synth = [ln for ln in lines if ln["status"] == "synth"]
    miss = sum(ln["status"] == "miss" for ln in lines)
    audio = sum(ln["audio_s"] for ln in lines if ln["status"] != "miss")
    compute = sum(ln["synth_s"] for ln in synth)
    if args.verbose and lines:
        print("\n  #  scene                  status  audio   lead  tail  maxgap  slnc/pause  "
              "overrun  unnarrated-before")
        for i, ln in enumerate(lines, 1):
            si = ln["silence"]
            sil = f"{si['lead']:5.2f} {si['tail']:5.2f}  {si['max_gap']:5.2f}" if si else "    -     -      - "
            print(f"  {i:<3}{ln['scene']:<23}{ln['status']:<8}{ln['audio_s']:5.1f}s  {sil}  "
                  f"{ln['slnc_ms']:>4}/{ln['pauses']:<5}  {ln['overrun_s']:6.1f}s  "
                  f"{ln['gap_before_s']:6.1f}s")
    if not args.quiet:
        for i, ln in enumerate(lines, 1):
            for why in narration_problems(ln):
                print(f"  ! line {i} {ln['scene']}: {why}  {ln['text'][:60]!r}")
    print("\nScenes (dry-run clock; animation run_times are estimates):")
    for name in names:
        if name in errors:
            print(f"  {name:<24} ERROR  {errors[name]}")
            continue
        sl = [ln for ln in lines if ln["scene"] == name]
        a = sum(ln["audio_s"] for ln in sl)
        m = sum(min(ln["motion_s"], ln["audio_s"]) for ln in sl)
        st = sum(ln["static_speech"] for ln in sl)
        print(f"  {name:<24} ~{scene_len[name]:6.1f}s  narration {a:6.1f}s in {len(sl)} lines, "
              f"unnarrated ~{max(scene_len[name] - a, 0):.1f}s  motion {100 * m / a if a else 100:.0f}%"
              + (f"  static_speech {st}" if st else ""))
    n = len(lines)
    total_a = sum(ln["audio_s"] for ln in lines)
    total_m = sum(min(ln["motion_s"], ln["audio_s"]) for ln in lines)
    n_static = sum(ln["static_speech"] for ln in lines)
    print(f"Sync: motion during {100 * total_m / total_a if total_a else 100:.0f}% of speech; "
          f"static_speech lines {n_static}/{n} (estimate: play() run_times, default 1s)")
    print(f"\nLines: {n}  cached {hits}/{n} ({100 * hits / n if n else 100:.0f}%)  synthesized {len(synth)}  "
          f"missing {miss}{' (estimated)' if miss else ''}")
    print(f"Audio: {audio:.1f}s  synth compute: {compute:.1f}s"
          + (f" ({compute / max(sum(l['audio_s'] for l in synth), 1e-9):.2f}s per audio-s)" if synth else "")
          + (f"  model load: {load['s']:.1f}s" if load["s"] else "")
          + f"  wall: {time.time() - t_wall:.1f}s")
    proof = None
    if not args.check and not args.no_proofread and lines:
        from studio import proofread
        why = proofread.available()
        if why:
            print(f"Proofread: skipped ({why})")
        else:
            proof = proofread.proofread_lines(lesson_dir, lines)
            proofread.print_summary(proof, lesson_dir)
    reports.append({
        "proofread": proofread_summary(proof),
        "lesson": str(lesson_dir), "engine": voice["engine"], "check": args.check,
        "lines": lines, "scene_len": scene_len,
        "errors": errors, "hits": hits, "synthesized": len(synth), "missing": miss,
        "audio_s": audio, "compute_s": compute, "load_s": load["s"],
        "wall_s": time.time() - t_wall})
    return 1 if errors else 0


def narration_check(lesson_dir: Path, names: list[str], voice: dict) -> dict | None:
    """Run `narrate --check` in a subprocess; returns its JSON report (None on failure)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "check.json"
        cmd = [sys.executable, "-P", "-m", "studio.build", "narrate", str(lesson_dir), "--check", "--quiet",
               "--engine", voice["engine"], "--json", str(out), *sum((["--scene", n] for n in names), [])]
        r = subprocess.run(cmd, env=scene_env(voice), capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            print(f"[narration check failed; rendering serially]\n{r.stderr[-2000:]}", file=sys.stderr)
            return None
        return json.loads(out.read_text())


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["narrate"]:
        return narrate(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", help="lesson folder name under the lessons dir, or a path to a lesson folder")
    ap.add_argument("--lessons-dir", help="default: $STUDY_LESSONS_DIR or $STUDY_HOME/lessons (~/study-videos/lessons)")
    ap.add_argument("--engine", choices=list(tts.ENGINES), help="override lesson.yaml's voice engine")
    ap.add_argument("--quality", "-q", choices=list(QUALITY_DIRS), default="l",
                    help="l=480p15 draft (default), m=720p30, h=1080p30 final, h60=1080p60, k=2160p60")
    ap.add_argument("--jobs", "-j", type=int, metavar="N",
                    help=f"parallel scene renders (default {default_jobs()} when all narration is cached "
                         "or the engine is say, else 1)")
    ap.add_argument("--cached-only", action="store_true",
                    help="fail instead of synthesizing narration (verify `study narrate` filled the cache)")
    ap.add_argument("--lock", action="append", metavar="DIR",
                    help="hold one of these mkdir locks (e.g. <collection>/locks/cpu1) while rendering")
    ap.add_argument("--owner", help="lock owner label (default: lesson folder name)")
    ap.add_argument("--scene", action="append", help="render only this scene (repeatable)")
    ap.add_argument("--frames", nargs="?", type=int, const=4, default=0, metavar="N",
                    help="dump N stills per rendered scene (default 4) to build/frames/")
    ap.add_argument("--no-render", action="store_true", help="skip rendering; just assemble / dump frames")
    ap.add_argument("--verbose", "-v", action="store_true", help="show Manim's own logs, progress and lock messages")
    ap.add_argument("--review", "--layout", dest="review", action="store_true",
                    help="record layout snapshots for `study review --layout` (needs -q l, --engine say, all scenes)")
    args = ap.parse_args(argv)
    global VERBOSE
    VERBOSE = args.verbose

    lesson_dir, spec = load_lesson(args.slug, args.lessons_dir)
    slug = lesson_dir.name
    try:
        voice = tts.voice_config(spec, lesson_dir, args.engine)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(str(e))
    all_names = [s["name"] for s in spec["scenes"]]
    names = args.scene or all_names
    unknown = set(names) - set(all_names)
    if unknown:
        sys.exit(f"not in lesson.yaml: {', '.join(sorted(unknown))}")

    if not args.no_render:
        status = tts.engine_status()[voice["engine"]]
        if not status.startswith("ok"):
            sys.exit(f"voice engine {voice['engine']}: {status}  (or pass --engine say)")

    failed = []
    problems = []
    t0 = time.time()
    if not args.no_render:
        jobs = args.jobs
        if jobs is None:
            jobs = default_jobs()
            if voice["engine"] != "say" and not args.cached_only:
                report = narration_check(lesson_dir, names, voice)
                missing = report["missing"] if report else -1
                if missing:
                    jobs = 1
                    note(f"Narration: {missing if missing > 0 else 'unknown number of'} uncached {voice['engine']} "
                         "lines -> rendering serially (run `study narrate` first to render in parallel)")
                else:
                    note(f"Narration: all {report['hits']} {voice['engine']} lines cached")
        jobs = max(1, min(jobs, len(names)))
        # Layout snapshots for `study review`: only a full 480p say draft is comparable to review's own build.
        record = args.review and not args.scene and args.quality == "l" and voice["engine"] == "say"
        if args.review and not record:
            print("note: --review skipped (needs -q l, --engine say and all scenes); review will rebuild its draft")
        review_key = None
        if record:
            from studio import review as review_tools
            review_key = review_tools.fingerprint(lesson_dir)  # before rendering, so edits during the build are caught
            out = lesson_dir / "build" / "review"
            out.mkdir(parents=True, exist_ok=True)
            (out / "layout-cache.json").unlink(missing_ok=True)
            os.environ["STUDIO_LAYOUT"] = str(out / "layout.jsonl")
        lock = None
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # run the finally block on kill
        try:
            lock = acquire_lock(args.lock, args.owner or lesson_dir.name) if args.lock else None
            failed = render_all(lesson_dir, names, args.quality, voice, jobs, args.verbose, args.cached_only)
        finally:
            for proc in list(_CHILDREN):  # interrupted: don't leave orphan renders behind
                proc.terminate()
            release_lock(lock)
            os.environ.pop("STUDIO_LAYOUT", None)
        if record and not failed:
            if review_tools.record_layout(lesson_dir, spec, review_key, "say"):
                note("layout snapshots recorded for `study review --layout`")
            else:
                problems.append("layout snapshots not recorded (each scene must inherit StudyScene and play/wait)")
    render_s = time.time() - t0
    if failed:
        print(f"\nRender FAILED for: {', '.join(failed)} (logs: "
              f"{', '.join(rel(log_path(lesson_dir, n, args.quality)) for n in failed)}). Not assembling.",
              file=sys.stderr)
        print(f"Render time: {render_s:.1f}s")
        return 1

    summary = []
    missing = [n for n in all_names if not scene_paths(lesson_dir, n, args.quality)[0].exists()]
    if missing:
        problems.append(f"no {QUALITY_DIRS[args.quality]} render yet for {', '.join(missing)}")
    else:
        # Only the lesson's own voice at a non-draft quality may write build/<slug>.mp4; a `say`
        # override (incl. review --layout's draft) or a 480p build goes to build/draft/.
        own_engine = tts.voice_config(spec, lesson_dir, None)["engine"]
        draft = args.quality == "l" or voice["engine"] != own_engine
        final = assemble(lesson_dir, slug, spec, args.quality,
                         lesson_dir / "build" / "draft" if draft else None)
        info = ffprobe(final)
        summary.append(f"Video: {rel(final)}  ({info['duration']:.1f}s, audio={info['audio']}, render {render_s:.1f}s)")
        if args.verbose:
            for f in ("captions.srt", "transcript.md", "chapters.txt"):
                print(f"       {rel(final.parent / f)}")
    if args.frames:
        frames = dump_frames(lesson_dir, names, args.quality, args.frames)
        summary.append(f"Frames: {len(frames)} in {rel(lesson_dir / 'build' / 'frames')}/")
    if args.verbose:
        print(f"Render time: {render_s:.1f}s")
    print("\n".join(summary))
    print(f"Problems: {'; '.join(problems) if problems else 'none'}")
    print(f"Logs: {rel(lesson_dir / 'build' / 'logs')}/  (per scene; add --verbose to stream Manim output)")
    return 0  # render failures returned 1 above; missing renders and layout notes are reported, as before


if __name__ == "__main__":
    raise SystemExit(main())
