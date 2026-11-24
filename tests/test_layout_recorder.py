"""LayoutRecorder must report the text a Text shows *now*, not a stale copy from an earlier animation."""
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_generation import _ManimTestCase


class _Renderer:
    time = 1.0


class _Scene:
    def __init__(self, *mobs):
        self.mobjects, self.renderer = list(mobs), _Renderer()


class RecorderTextTests(_ManimTestCase):
    def rows(self, path):
        return [json.loads(l) for l in Path(path).read_text().splitlines()]

    def test_fade_in_then_in_place_change_reports_new_text_and_size(self):
        from manim import FadeIn
        from studio.cslib import cross_fade, label
        from studio.review import LayoutRecorder
        with tempfile.TemporaryDirectory() as d:
            t = label("ACK 1101 (resent)", size=22, mono=True)
            scene = _Scene(t)
            rec = LayoutRecorder(Path(d) / "layout.jsonl", scene)
            fade = FadeIn(t); fade.begin(); fade.finish()
            rec.record([fade])
            change = cross_fade(t, label("ACK 1101 · resent once", size=22, mono=True))
            change.begin(); change.finish()
            rec.record([change])
            last = self.rows(rec.path)[-1]["boxes"][0]
            self.assertEqual(last["text"], "ACK 1101 · resent once")
            self.assertAlmostEqual(last["font_size"], 22.0, places=3)

    def test_real_transform_still_reports_the_target_text(self):
        from manim import Transform
        from studio.cslib import label
        from studio.review import LayoutRecorder
        with tempfile.TemporaryDirectory() as d:
            t = label("before", size=24)
            rec = LayoutRecorder(Path(d) / "layout.jsonl", _Scene(t))
            anim = Transform(t, label("after", size=24))
            anim.begin(); anim.finish()
            rec.record([anim])
            self.assertEqual(self.rows(rec.path)[-1]["boxes"][0]["text"], "after")


if __name__ == "__main__":
    unittest.main()
