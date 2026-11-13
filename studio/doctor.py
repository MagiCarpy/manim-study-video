"""Check that everything the pipeline needs is installed.

    study doctor

Exit status 0 when all required pieces are present (optional ones only warn).
"""

from __future__ import annotations

import importlib.util
import platform
import re
import shutil
import subprocess
import sys

from studio.paths import SKILL_DIR, lessons_dir


def _run(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv=None) -> int:
    ok = True

    def check(name: str, good: bool, detail: str = "", required: bool = True) -> None:
        nonlocal ok
        mark = "ok  " if good else ("FAIL" if required else "warn")
        ok &= good or not required
        print(f"  [{mark}] {name}{': ' + detail if detail else ''}")

    print(f"skill dir:   {SKILL_DIR}")
    print(f"lessons dir: {lessons_dir()}  (override with --lessons-dir or $STUDY_LESSONS_DIR)")
    print(f"platform:    {platform.system()} {platform.mac_ver()[0] or platform.release()} {platform.machine()}")
    print("\nTools")
    check("uv", bool(shutil.which("uv")), _run(["uv", "--version"]) or "brew install uv")
    check("ffmpeg / ffprobe", bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
          "" if shutil.which("ffmpeg") else "brew install ffmpeg")
    pc = shutil.which("pkg-config")
    for lib in ("cairo", "pango"):
        ver = _run(["pkg-config", "--modversion", lib]) if pc else None
        check(f"{lib} (pkg-config)", ver is not None, ver or f"brew install {lib} pkgconf")
    check("pdftoppm (optional; ingest uses PyMuPDF)", bool(shutil.which("pdftoppm")),
          "" if shutil.which("pdftoppm") else "brew install poppler", required=False)
    check("Keynote.app (optional; PPTX slide images)", bool(_run(["mdfind", "kMDItemCFBundleIdentifier == 'com.apple.iWork.Keynote'"])),
          required=False)

    print("\nPython env")
    venv = SKILL_DIR / ".venv"
    check("skill venv", sys.prefix == str(venv) or venv.exists(), str(venv))
    check("python 3.12", sys.version_info[:2] == (3, 12), sys.version.split()[0])
    for mod in ("manim", "manim_voiceover", "pymupdf", "pptx", "yaml"):
        check(mod, importlib.util.find_spec(mod) is not None, "" if importlib.util.find_spec(mod) else "study setup")
    try:
        import PIL
        check("pillow < 12", int(PIL.__version__.split(".")[0]) < 12, PIL.__version__)
    except ImportError:
        check("pillow", False, "study setup")

    print("\nVoice engines (lesson.yaml `voice: {engine: ...}`)")
    from studio.tts import engine_status
    for name, status in engine_status().items():
        check(name, status.startswith("ok"), status, required=(name == "say"))
    from studio import proofread
    why = proofread.available()
    check("proofread", why is None, why or f"ok ({proofread.MODEL}; runs after `study narrate`)", required=False)
    from studio import voices as presets
    names = presets.list_presets()
    print(f"         fish voice presets ({presets.VOICES_DIR}): "
          + (", ".join(f"{n}{' (default)' if n == presets.DEFAULT_PRESET else ''}" for n in names)
             or f"none ('{presets.DEFAULT_PRESET}' is auto-created on first fish build)"))
    lfm3 = sorted(p.stem for p in presets.VOICES_DIR.glob("lfm3_*.yaml"))
    print("         lfm3 voice presets: " + (", ".join(lfm3) or "none (`study voice audition --engine lfm3 --save NAME`)"))
    voices = _run(["say", "-v", "?"]) or ""
    en = [m.group(1) for m in re.finditer(r"^(.+?)\s+en_\w+", voices, re.M)]
    if en:
        print(f"         say voices (en): {len(en)}, e.g. {', '.join(en[:6])}")

    print("\nAll required checks passed." if ok else "\nSome required checks failed (see FAIL above).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
