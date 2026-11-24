"""StudyScene: the base class every lesson scene should inherit from."""

from __future__ import annotations

import time
import os
from contextlib import contextmanager
from pathlib import Path

from manim import DOWN, UP, FadeIn, FadeOut, Text, VGroup, Write
from manim_voiceover import VoiceoverScene
from manim_voiceover.helper import remove_bookmarks

from studio import style
from studio.tts import caption_text, make_service

style.apply_theme()


class StudyScene(VoiceoverScene):
    """VoiceoverScene with the house style and offline narration (engine from lesson.yaml `voice:`).

    Override `construct()` as usual. Narrate with:

        with self.voiceover(text="...") as tracker:
            self.play(Create(x), run_time=tracker.duration)

    The block waits for the narration to finish before continuing.

    `study narrate` sets `StudyScene.dry_run` to a `DryRun`: construct() then runs
    without rendering (play/wait only advance a virtual clock) while voiceover()
    synthesizes (or, with --check, only looks up) each line into the same cache
    a render uses, and records it for the timing report.
    """

    dry_run: "DryRun | None" = None

    def setup(self):
        super().setup()
        self._layout_recorder = None
        if os.environ.get("STUDIO_LAYOUT") and self.dry_run is None:
            from studio.review import LayoutRecorder
            self._layout_recorder = LayoutRecorder(os.environ["STUDIO_LAYOUT"], self)
        if self.dry_run is not None:
            self.set_speech_service(self.dry_run.service, create_subcaption=False)
            self._dry_t = 0.0
        else:
            self.set_speech_service(make_service())

    def voiceover(self, text=None, **kwargs):
        if self.dry_run is not None:
            return self._dry_voiceover(text, **kwargs)
        if text is not None and getattr(self, "_layout_recorder", None) is not None:
            return self._layout_voiceover(text, **kwargs)
        if text is not None:
            kwargs.setdefault("subcaption", caption_text(text))
        return super().voiceover(text=text, **kwargs)

    @contextmanager
    def _layout_voiceover(self, text, **kwargs):
        recorder = self._layout_recorder
        previous = recorder.narration
        recorder.narration = text
        kwargs.setdefault("subcaption", caption_text(text))
        try:
            with super().voiceover(text=text, **kwargs) as tracker:
                yield tracker
        finally:
            recorder.narration = previous

    # --- dry run (study narrate) ----------------------------------------------
    @contextmanager
    def _dry_voiceover(self, text=None, **kwargs):
        if text is None:
            raise ValueError("study narrate supports voiceover(text=...) only")
        tracker = self.dry_run.voiceover(self, text)
        self.current_tracker = tracker
        try:
            yield tracker
        finally:
            self.wait_for_voiceover()
            self.dry_run.lines[-1]["block_end"] = self._dry_t

    def play(self, *args, **kwargs):
        if self.dry_run is None:
            result = super().play(*args, **kwargs)
            recorder = getattr(self, "_layout_recorder", None)
            if recorder is not None:
                recorder.record(args)
            return result
        rt = kwargs.get("run_time")
        if rt is None:
            rts = []
            for a in args:
                r = getattr(a, "run_time", None)
                if r is None:  # `mob.animate...` builder
                    r = (getattr(a, "anim_args", None) or {}).get("run_time")
                rts.append(float(r) if isinstance(r, (int, float)) else 1.0)
            rt = max(rts, default=1.0)
        self._dry_t += float(rt)
        lines = self.dry_run.lines
        if lines and "block_end" not in lines[-1]:  # inside an open voiceover block: on-screen motion
            lines[-1]["motion_s"] = lines[-1].get("motion_s", 0.0) + float(rt)
            lines[-1]["beats"] = lines[-1].get("beats", 0) + 1

    def wait(self, duration=1.0, *args, **kwargs):
        if self.dry_run is None:
            result = super().wait(duration, *args, **kwargs)
            recorder = getattr(self, "_layout_recorder", None)
            if recorder is not None:
                recorder.record()
            return result
        self._dry_t += float(duration)

    def wait_until(self, *args, **kwargs):
        if self.dry_run is None:
            return super().wait_until(*args, **kwargs)

    def add_sound(self, *args, **kwargs):
        if self.dry_run is None:
            return super().add_sound(*args, **kwargs)

    def add_subcaption(self, *args, **kwargs):
        if self.dry_run is None:
            return super().add_subcaption(*args, **kwargs)

    # --- small conveniences -------------------------------------------------
    def section_title(self, title: str, subtitle: str | None = None) -> VGroup:
        """Show a heading at the top edge and return it (caller removes it)."""
        head = Text(title, font=style.FONT, font_size=style.HEADING_SIZE, color=style.BLUE, weight="BOLD")
        group = VGroup(head)
        if subtitle:
            sub = Text(subtitle, font=style.FONT, font_size=style.LABEL_SIZE, color=style.DIM)
            group.add(sub.next_to(head, DOWN, buff=0.15))
        group.to_edge(UP, buff=0.55)
        self.play(Write(head), *[FadeIn(m) for m in group[1:]], run_time=0.8)
        return group

    def clear_all(self, run_time: float = 0.6):
        if self.mobjects:
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=run_time)

    def wait_for(self, t, mark: str | None = None, min_gap: float = 0.05):
        """Wait until bookmark `mark` (or the narration's end); skip gaps under min_gap.

        with self.voiceover(text="Here it is. <bookmark mark='b'/>And here.") as t:
            self.play(FadeIn(a)); self.wait_for(t, "b"); self.play(FadeIn(b)); self.wait_for(t)
        """
        d = t.time_until_bookmark(mark) if mark else t.get_remaining_duration()
        if d > min_gap:
            self.wait(d)


class DryTracker:
    """Stand-in for manim-voiceover's VoiceoverTracker on the dry-run clock."""

    def __init__(self, scene: StudyScene, text: str, duration: float, word_boundaries=None):
        from manim_voiceover.tracker import VoiceoverTracker

        self.scene = scene
        self.duration = duration
        self.start_t = scene._dry_t
        self.end_t = self.start_t + duration
        self.data = {"input_text": text, "word_boundaries": word_boundaries or []}
        self.bookmark_times = {}
        if "<bookmark" in text:
            # reuse the real bookmark math with renderer time pinned to our clock
            fake = type("S", (), {"renderer": type("R", (), {"time": self.start_t})()})()
            vt = VoiceoverTracker.__new__(VoiceoverTracker)
            vt.scene, vt.data, vt.duration = fake, dict(self.data), duration
            vt.start_t, vt.end_t = self.start_t, self.end_t
            vt._process_bookmarks()
            self.bookmark_times = vt.bookmark_times

    def get_remaining_duration(self, buff: float = 0.0) -> float:
        return max(self.end_t - self.scene._dry_t + buff, 0.0)

    def time_until_bookmark(self, mark: str, buff: float = 0.0, limit: float | None = None) -> float:
        if mark not in self.bookmark_times:
            raise Exception("There is no <bookmark mark='%s' />" % mark)
        r = max(self.bookmark_times[mark] - self.scene._dry_t + buff, 0.0)
        return r if limit is None else min(limit, r)


class DryRun:
    """Collects narration lines for `study narrate`. With `check=True` nothing is
    synthesized or written; uncached lines get an estimated duration (~2.6 words/s)."""

    def __init__(self, service, check: bool = False, on_line=None):
        self.service = service
        self.check = check
        self.on_line = on_line
        self.lines: list[dict] = []
        self.scene_name = ""

    def voiceover(self, scene: StudyScene, text: str) -> DryTracker:
        from studio import tts

        svc = self.service
        norm = " ".join(text.split())
        cached = svc.lookup(norm)
        line = {"scene": self.scene_name, "text": caption_text(text), "raw": norm, "status": "hit" if cached else "miss",
                "synth_s": 0.0, "start": scene._dry_t, "wav": None}
        if cached is None and not self.check:
            t0 = time.time()
            data = svc._wrap_generate_from_text(text)
            line["synth_s"] = time.time() - t0
            line["status"] = "synth"
            cached = data
        if cached is not None:
            wav = Path(svc.cache_dir) / cached["final_audio"]
            line["wav"] = str(wav)
            from manim_voiceover.modify_audio import get_duration
            duration = get_duration(wav)
            wb = cached.get("word_boundaries") or tts.approx_word_boundaries(remove_bookmarks(norm), wav)
        else:
            duration = max(len(remove_bookmarks(norm).split()) / 2.6, 0.5)
            wb = None
        line["audio_s"] = duration
        self.lines.append(line)
        if self.on_line:
            self.on_line(line)
        return DryTracker(scene, norm, duration, wb)
