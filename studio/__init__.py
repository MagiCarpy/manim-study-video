"""Slides -> narrated, animated study videos (Manim + offline TTS: macOS `say` or Fish S2 Pro)."""

import shutil
import sys
import types
import warnings

# manim-voiceover imports `sox` at module load, but only uses it for
# SpeechService(global_speed != 1), which we never do (set `rate`/`speed`
# in lesson.yaml instead). Without the SoX binary that import prints noisy warnings, so stub it.
if "sox" not in sys.modules and shutil.which("sox") is None:
    _sox = types.ModuleType("sox")

    class _NoSox:
        def __init__(self, *a, **k):
            raise RuntimeError("SoX is not installed; set the narration speed via lesson.yaml `rate` instead.")

    _sox.Transformer = _NoSox
    sys.modules["sox"] = _sox

# pydub emits SyntaxWarnings on Python 3.12; harmless.
warnings.filterwarnings("ignore", category=SyntaxWarning)
