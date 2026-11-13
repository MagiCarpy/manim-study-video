"""Fish voice presets: a fixed reference clip so every line has the same speaker.

    study voice list
    study voice audition [--n 4] [--instruct "..."] [--text "..."] [--seed S] [--out DIR]
    study voice save <name> <clip.wav> [--text "exact transcript"] [--force]

Without a reference clip Fish S2 Pro invents a new random speaker for every
utterance (the per-line seed doesn't help: different text -> different voice).
A preset is `$SKILL/voices/<name>.wav` (~10 s, mono 24 kHz 16-bit) + `<name>.txt`
(its exact transcript) + optional `<name>.yaml` (how it was made). Lessons use
it with `voice: {engine: fish, preset: narrator}`; fish defaults to `narrator`.

`audition` renders N candidates of one sentence with different seeds (no
reference) and prints their stats; listen, then `save` the one you like.

LFM3 (`--engine lfm3`) cannot clone: a voice is locale + gender + seed, and the
speaker drifts with the seed. Its presets are `voices/lfm3_<name>.yaml`
({engine: lfm3, locale, gender, seed, consistency stats}); pick the seed with

    study voice audition --engine lfm3 --locale en-US --gender male --seeds 3 11 12 [--save lfm3_us_male]

which speaks the same ~10 lesson lines with each seed (one model load) and
reports the per-line median pitch spread; `--save` keeps the steadiest seed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import yaml

from studio.paths import SKILL_DIR

VOICES_DIR = SKILL_DIR / "voices"
DEFAULT_PRESET = "narrator"
# No default style instruction: with mlx-audio 0.6 + this checkpoint, `instruct` is often
# *spoken aloud* ("Style instruction: calm ...") or replaces the text. The register comes
# from the sentence itself instead.
DEFAULT_INSTRUCT = None
# ~11 s at a lecturer's pace, neutral register, varied vowels/consonants and a contrast.
REF_TEXT = ("Welcome back. Today we'll explore how data travels across a network, from a quiet "
            "laptop to a busy server. Each step is simple, but together they form a surprisingly "
            "elegant system.")
AUDITION_DIR = Path(tempfile.gettempdir()) / "study-voice-audition"
DEFAULT_LFM3_PRESET = "lfm3_us_female"
# Lines from examples/_smoke_test (varied length/jargon) for the LFM3 seed-consistency study.
CONSISTENCY_LINES = [
    "Here's the slide we're starting from: TCP connection setup.",
    "The key idea is this line: a three-way handshake of SYN, SYN-ACK, and ACK.",
    "Two hosts: a client, which starts closed, and a server, listening.",
    "First, the client sends a SYN carrying its initial sequence number, x. It is now in the SYN-sent state.",
    "The client is now established, and acknowledges y plus one.",
    "Now round robin. Three processes wait in the ready queue, and each may run for at most two time units.",
    "P1 runs for one quantum, then goes to the back of the queue.",
    "P3 needs only one unit, so it finishes early.",
    "Average waiting time: three, five and four, so four time units.",
    "And round robin trades responsiveness against context-switch overhead.",
]


def lfm3_preset(name: str) -> dict:
    """{"locale", "gender", "seed"} from voices/<name>.yaml (LFM3 has no reference clip)."""
    path = VOICES_DIR / f"{name}.yaml"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in VOICES_DIR.glob("lfm3_*.yaml"))) or "none"
        raise FileNotFoundError(f"lfm3 voice preset {name!r} not found in {VOICES_DIR} (have: {have}); "
                                f"make one with `study voice audition --engine lfm3 ... --save {name}`")
    meta = yaml.safe_load(path.read_text()) or {}
    if meta.get("engine") != "lfm3":
        raise ValueError(f"{path} is not an lfm3 preset (engine: {meta.get('engine')})")
    return {k: meta[k] for k in ("locale", "gender", "seed", "speed") if k in meta}


def lfm3_study(locale: str, gender: str, seeds: list[int], lines: list[str] = CONSISTENCY_LINES,
               out: Path | None = None) -> list[dict]:
    """Speak `lines` once per seed (one model load); per-seed pitch spread across lines."""
    import statistics

    from studio.tts import lfm3_synthesize

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        base = out or Path(tmp)
        for seed in seeds:
            d = base / f"lfm3_{locale}_{gender}_seed{seed}"
            d.mkdir(parents=True, exist_ok=True)
            f0s, audio, comp, wpms, peaks = [], 0.0, 0.0, [], []
            for i, text in enumerate(lines):
                wav = d / f"line{i + 1:02d}.wav"
                t0 = time.time()
                lfm3_synthesize(text, wav, locale=locale, gender=gender, seed=seed)
                comp += time.time() - t0
                st = clip_stats(wav, text)
                f0s.append(st["f0"])
                audio += st["duration"]
                wpms.append(st["wpm"])
                peaks.append(st["peak"])
            med = statistics.median(f0s)
            rows.append({"locale": locale, "gender": gender, "seed": seed, "lines": len(lines),
                         "f0_median": round(med, 1), "f0_stdev": round(statistics.pstdev(f0s), 1),
                         "f0_min": round(min(f0s), 1), "f0_max": round(max(f0s), 1),
                         "f0_max_dev": round(max(abs(f - med) for f in f0s), 1),
                         "wpm_median": statistics.median(wpms), "peak_max": max(peaks),
                         "audio_s": round(audio, 1), "rtf": round(comp / audio, 2) if audio else None,
                         "dir": str(d) if out else None})
    return rows


def preset_paths(name: str) -> tuple[Path, Path, Path]:
    return VOICES_DIR / f"{name}.wav", VOICES_DIR / f"{name}.txt", VOICES_DIR / f"{name}.yaml"


def list_presets() -> list[str]:
    return sorted(p.stem for p in VOICES_DIR.glob("*.wav") if p.with_suffix(".txt").exists())


def preset_ref(name: str) -> dict:
    """{"ref_audio", "ref_text"} for a preset; creates the default one if missing."""
    wav, txt, _ = preset_paths(name)
    if not (wav.exists() and txt.exists()):
        if name != DEFAULT_PRESET:
            have = ", ".join(list_presets()) or "none"
            raise FileNotFoundError(f"fish voice preset {name!r} not found in {VOICES_DIR} (have: {have}); "
                                    f"make one with `study voice audition` + `study voice save {name} ...`")
        print(f"[voice] preset {name!r} missing: auditioning 4 seeds and keeping the best "
              f"(swap later with `study voice save {name} ...`)", file=sys.stderr, flush=True)
        create_default()
    return {"ref_audio": str(wav), "ref_text": txt.read_text(encoding="utf-8").strip()}


# --- clip stats (for audition and auto-pick) -----------------------------------------
def _read_mono(path: Path):
    import numpy as np

    with wave.open(str(path)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32768
    return (x.reshape(-1, ch).mean(1) if ch > 1 else x), sr


def median_f0(x, sr: int, fmin: float = 60, fmax: float = 400) -> float:
    """Median pitch over voiced frames (YIN cumulative-mean-normalized difference)."""
    import numpy as np

    x = np.interp(np.arange(0, len(x) / sr, 1 / 16000), np.arange(len(x)) / sr, x)  # -> 16 kHz
    sr, frame = 16000, 1024
    tmin, tmax = int(sr / fmax), int(sr / fmin)
    floor = 0.3 * np.sqrt(np.mean(x ** 2))
    f0 = []
    for i in range(0, len(x) - frame - tmax, 160):
        seg, w = x[i:i + frame + tmax], x[i:i + frame]
        if np.sqrt(np.mean(w ** 2)) < floor:
            continue
        c = np.concatenate([[0], np.cumsum(seg ** 2)])
        lag = np.arange(tmax + 1)
        d = np.sum(w ** 2) + c[lag + frame] - c[lag] - 2 * np.correlate(seg, w, "valid")[:tmax + 1]
        cm = d[1:] * lag[1:] / (np.cumsum(d[1:]) + 1e-12)
        hit = np.nonzero(cm[tmin - 1:tmax - 1] < 0.15)[0]
        if len(hit):
            tau = hit[0] + tmin
            while tau < tmax and cm[tau] < cm[tau - 1]:  # cm[k] is lag k+1
                tau += 1
            f0.append(sr / tau)
    return float(np.median(f0)) if f0 else 0.0


def clip_stats(path: Path, text: str) -> dict:
    import numpy as np

    x, sr = _read_mono(path)
    dur = len(x) / sr
    return {"duration": round(dur, 2), "peak": round(float(np.abs(x).max()), 3),
            "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)), 1),
            "wpm": round(len(text.split()) / dur * 60) if dur else 0,
            "f0": round(median_f0(x, sr), 1)}


def problems(s: dict) -> list[str]:
    """Why a candidate is unfit as a reference (empty = fine)."""
    out = []
    if not 6 <= s["duration"] <= 16:
        out.append(f"duration {s['duration']}s outside 6-16 s")
    if not 120 <= s["wpm"] <= 210:
        out.append(f"{s['wpm']} wpm (truncated/garbled?)")
    if s["peak"] >= 0.99:
        out.append("clipped")
    if not -30 <= s["rms_db"] <= -12:
        out.append(f"loudness {s['rms_db']} dBFS")
    if not 75 <= s["f0"] <= 260:
        out.append(f"pitch {s['f0']} Hz")
    return out


def pick(cands: list[dict]) -> dict:
    """Fewest problems, then the most typical pitch among candidates (median F0), loudness near
    -20 dBFS and a lecturer's pace (~160 wpm; the reference's pace carries over to narration)."""
    import statistics

    mid = statistics.median(c["stats"]["f0"] for c in cands)
    return min(cands, key=lambda c: (len(problems(c["stats"])), abs(c["stats"]["f0"] - mid) / mid
                                     + abs(c["stats"]["rms_db"] + 20) / 40 + abs(c["stats"]["wpm"] - 160) / 160))


# --- commands -----------------------------------------------------------------------
def audition(n: int = 4, instruct: str | None = DEFAULT_INSTRUCT, text: str = REF_TEXT,
             seed: int = 0, out: Path = AUDITION_DIR, temperature: float = 0.7) -> list[dict]:
    from studio.tts import FISH_MODEL, fish_synthesize

    out.mkdir(parents=True, exist_ok=True)
    cands = []
    for s in range(seed, seed + n):
        wav = out / f"seed{s}.wav"
        t0 = time.time()
        fish_synthesize(text, wav, seed=s, instruct=instruct, temperature=temperature)
        meta = {"text": text, "model": FISH_MODEL, "seed": s, "instruct": instruct, "temperature": temperature,
                "gen_seconds": round(time.time() - t0, 1), "stats": clip_stats(wav, text)}
        wav.with_suffix(".yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
        cands.append({"wav": wav, **meta})
    return cands


def save(name: str, src: Path, text: str | None = None, force: bool = False, meta: dict | None = None) -> Path:
    """Store `src` as preset `name` (mono 24 kHz 16-bit). Audition sidecars supply text/meta."""
    side = src.with_suffix(".yaml")
    if meta is None and side.exists():
        meta = yaml.safe_load(side.read_text()) or {}
    meta = dict(meta or {})
    text = (text or meta.get("text") or "").strip()
    if not text:
        sys.exit("need --text: the exact words spoken in the clip (Fish conditions on clip + transcript)")
    wav, txt, info = preset_paths(name)
    if wav.exists() and not force:
        sys.exit(f"preset {name!r} exists ({wav}); pass --force to replace it")
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "24000",
                    "-sample_fmt", "s16", str(wav)], check=True)
    txt.write_text(text + "\n", encoding="utf-8")
    meta.pop("text", None)
    meta.update(source=meta.get("source") or ("audition" if "seed" in meta else str(src.name)),
                stats=clip_stats(wav, text))
    info.write_text(yaml.safe_dump(meta, sort_keys=False))
    for p in problems(meta["stats"]):
        print(f"  warning: {p}", file=sys.stderr)
    return wav


def create_default() -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        cands = audition(4, out=Path(tmp))
        best = pick(cands)
        meta = {k: v for k, v in best.items() if k not in ("wav", "stats")}
        meta["source"] = "audition (auto-picked)"
        path = save(DEFAULT_PRESET, best["wav"], force=True, meta=meta)
    print(f"[voice] saved {path} (seed {best['seed']}, {best['stats']})", file=sys.stderr, flush=True)
    return path


def _fmt(s: dict) -> str:
    return f"{s['duration']:5.1f}s  F0 {s['f0']:5.1f} Hz  {s['rms_db']:5.1f} dBFS  peak {s['peak']:.2f}  {s['wpm']} wpm"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["proofread"]:
        from studio import proofread
        return proofread.main(argv[1:])
    ap = argparse.ArgumentParser(prog="study voice", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list presets")
    sub.add_parser("proofread", help="transcribe narration with Whisper and flag misread words (see --help)")
    a = sub.add_parser("audition", help="render candidate voices (different seeds, no reference)")
    a.add_argument("--n", type=int, default=4)
    a.add_argument("--seed", type=int, default=0, help="first seed (candidates use seed..seed+n-1)")
    a.add_argument("--instruct", default=DEFAULT_INSTRUCT,
                   help="style instruction (often spoken aloud by this model; listen before saving)")
    a.add_argument("--text", default=REF_TEXT, help="sentence to speak (~10 s)")
    a.add_argument("--out", type=Path, default=None, help=f"default: {AUDITION_DIR} (fish), temp (lfm3)")
    a.add_argument("--engine", choices=["fish", "lfm3"], default="fish")
    a.add_argument("--locale", default="en-US", help="lfm3: en-US | en-GB")
    a.add_argument("--gender", default="female", help="lfm3: female | male")
    a.add_argument("--seeds", type=int, nargs="+", default=[3, 11, 12], help="lfm3 seeds to compare")
    a.add_argument("--save", metavar="NAME", help="lfm3: save the steadiest seed as preset NAME")
    s = sub.add_parser("save", help="store a clip as preset <name>")
    s.add_argument("name")
    s.add_argument("wav", type=Path, help="audition candidate or your own recording")
    s.add_argument("--text", help="exact transcript (required for your own recordings)")
    s.add_argument("--force", action="store_true", help="replace an existing preset")
    args = ap.parse_args(argv)

    if args.cmd == "list":
        names = list_presets()
        print(f"presets in {VOICES_DIR}:" if names else f"no presets in {VOICES_DIR}")
        for name in names:
            wav, txt, info = preset_paths(name)
            meta = yaml.safe_load(info.read_text()) if info.exists() else {}
            how = f"seed {meta['seed']}" if "seed" in meta else meta.get("source", "")
            print(f"  {name:12s} {_fmt(clip_stats(wav, txt.read_text()))}  {how}"
                  f"{'  (default)' if name == DEFAULT_PRESET else ''}")
        for path in sorted(VOICES_DIR.glob("lfm3_*.yaml")):
            meta = yaml.safe_load(path.read_text()) or {}
            row = next((r for r in meta.get("consistency", []) if r.get("seed") == meta.get("seed")), {})
            print(f"  {path.stem:16s} lfm3 {meta.get('locale')} {meta.get('gender')} seed {meta.get('seed')}"
                  + (f"  F0 {row['f0_median']} Hz (stdev {row['f0_stdev']} over {row['lines']} lines)" if row else ""))
    elif args.cmd == "audition" and args.engine == "lfm3":
        rows = lfm3_study(args.locale, args.gender, args.seeds, out=args.out)
        print(f"\nLFM3 {args.locale} {args.gender}: per-line median F0 over {rows[0]['lines']} lines")
        for r in rows:
            print(f"  seed {r['seed']:<4} median {r['f0_median']:6.1f} Hz  stdev {r['f0_stdev']:5.1f}  "
                  f"range {r['f0_min']:.0f}-{r['f0_max']:.0f}  max dev {r['f0_max_dev']:5.1f}  "
                  f"{r['wpm_median']} wpm  peak {r['peak_max']:.2f}  RTF {r['rtf']}")
        best = min(rows, key=lambda r: (r["f0_stdev"], r["f0_max_dev"]))
        print(f"steadiest: seed {best['seed']}" + (f"  (clips in {args.out}/)" if args.out else ""))
        if args.save:
            path = VOICES_DIR / f"{args.save}.yaml"
            path.write_text(yaml.safe_dump({
                "engine": "lfm3", "locale": args.locale, "gender": args.gender, "seed": best["seed"],
                "source": "study voice audition --engine lfm3 (steadiest per-line median F0)",
                "consistency": [{k: v for k, v in r.items() if k != "dir"} for r in rows]}, sort_keys=False))
            print(f"saved preset {args.save!r}: {path}")
    elif args.cmd == "audition":
        cands = audition(args.n, args.instruct or None, args.text, args.seed, args.out or AUDITION_DIR)
        best = pick(cands)
        print(f"\ncandidates in {args.out}/  (listen, e.g. `afplay {cands[0]['wav']}`)")
        for c in cands:
            bad = problems(c["stats"])
            mark = "*" if c is best else " "
            print(f" {mark} {c['wav'].name:10s} {_fmt(c['stats'])}  gen {c['gen_seconds']}s"
                  f"{'  [' + '; '.join(bad) + ']' if bad else ''}")
        print(f"\n* = auto-pick. Keep one:  study voice save <name> {best['wav']}")
    elif args.cmd == "save":
        if not args.wav.is_file():
            sys.exit(f"no such file: {args.wav}")
        path = save(args.name, args.wav, args.text, args.force)
        print(f"saved preset {args.name!r}: {path} (+ .txt, .yaml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
