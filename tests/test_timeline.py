"""Timeline (two-or-more lifeline sequence diagrams) and the timing/text helpers lessons kept re-implementing."""
import unittest

from tests.test_generation import _ManimTestCase


class FakeTracker:
    """Stand-in for a voiceover tracker: bookmarks at fixed offsets."""

    def __init__(self, remaining=4.0, marks=None):
        self.remaining, self.marks = remaining, marks or {}

    def get_remaining_duration(self, buff=0.0):
        return self.remaining

    def time_until_bookmark(self, mark, buff=0.0, limit=None):
        return self.marks[mark]


class TimelineGeometryTests(_ManimTestCase):
    def make(self, **kw):
        from studio.cslib import Timeline
        return Timeline(("Client", "Server"), **kw)

    def test_message_runs_between_lifelines_with_slant_and_upright_label_above(self):
        import numpy as np
        tl = self.make(x=(-3, 3), top=2.6, bottom=-3.0, row=0.85, slant=0.3)
        m = tl.message(0, "Client", "Server", "SYN seq 1000")
        np.testing.assert_allclose(m.start[:2], (-3, tl.y(0)))
        np.testing.assert_allclose(m.end[:2], (3, tl.y(0) - 0.3))
        back = tl.message(1, "Server", "Client", "SYN+ACK")
        np.testing.assert_allclose(back.start[:2], (3, tl.y(1)))
        self.assertAlmostEqual(tl.y(1), tl.y(0) - 0.85)
        # Label is horizontal (never rotated) and clears the arrow where it sits.
        from studio.cslib import label
        self.assertAlmostEqual(m.text.width, label("SYN seq 1000", size=22, mono=True).width, places=5)
        lx = m.label.get_center()[0]
        frac = (lx - m.start[0]) / (m.end[0] - m.start[0])
        arrow_y = m.start[1] + frac * (m.end[1] - m.start[1])
        self.assertGreater(m.label.get_bottom()[1], arrow_y)

    def test_label_has_background_plate_behind_text(self):
        from studio import style
        from manim import ManimColor
        tl = self.make()
        m = tl.message(0, "Client", "Server", "ACK 1001")
        plate, text = m.label[0], m.label[1]
        self.assertGreaterEqual(plate.width, text.width)
        self.assertLess(plate.z_index, text.z_index)
        self.assertEqual(plate.get_fill_color().to_hex().lower(), ManimColor(style.BG).to_hex().lower())

    def test_rich_label_is_one_text_coloured_by_part(self):
        from studio import style
        from manim import ManimColor
        tl = self.make()
        m = tl.message(0, "Client", "Server", [("SYN", style.GOLD), ("seq 1000", style.FG)])
        glyphs = m.text.submobjects            # one Text: shared baseline, no hand spacing
        self.assertEqual(len(glyphs), len("SYNseq1000"))
        hexes = [g.get_color().to_hex().lower() for g in glyphs]
        self.assertEqual(hexes[:3], [ManimColor(style.GOLD).to_hex().lower()] * 3)
        self.assertEqual(set(hexes[3:]), {ManimColor(style.FG).to_hex().lower()})

    def test_kinds_set_style_old_duplicates_are_dashed_and_dim(self):
        from studio import style
        from manim import ManimColor
        tl = self.make()
        old = tl.message(0, "Client", "Server", "Hi, 13", kind="old")
        real = tl.message(1, "Server", "Client", "Hi")
        resend = tl.message(2, "Client", "Server", "Data 2", kind="retransmit")
        self.assertGreater(len(old.dashes), 3)
        self.assertEqual(len(real.dashes), 1)
        hexof = lambda m: m.dashes[0].get_color().to_hex().lower()
        self.assertEqual(hexof(old), ManimColor(style.DIM).to_hex().lower())
        self.assertEqual(hexof(real), ManimColor(style.FG).to_hex().lower())
        self.assertEqual(hexof(resend), ManimColor(style.YELLOW).to_hex().lower())
        with self.assertRaises(ValueError):
            tl.message(3, "Client", "Server", "x", kind="sideways")

    def test_lost_message_stops_short_and_carries_a_red_cross(self):
        import numpy as np
        from studio import style
        from manim import ManimColor
        tl = self.make(x=(-3, 3))
        m = tl.message(0, "Server", "Client", "ACK 3002", lost_at=0.55)
        full = np.array([-3.0, tl.y(0) - tl.slant, 0])
        expected = m.start + (full - m.start) * 0.55
        np.testing.assert_allclose(m.end, expected)
        self.assertIsNotNone(m.cross)
        self.assertEqual(m.cross.get_color().to_hex().lower(), ManimColor(style.RED).to_hex().lower())
        self.assertLess(m.cross.get_center()[0], m.end[0])  # just past the stop, in travel direction

    def test_rows_that_overflow_the_lifelines_are_rejected(self):
        tl = self.make(top=2.6, bottom=-1.2, row=0.85)
        tl.message(3, "Client", "Server", "fits")
        with self.assertRaises(ValueError):
            tl.message(4, "Client", "Server", "too low")

    def test_whole_diagram_fits_the_safe_area(self):
        from manim import VGroup
        tl = self.make(x=(-5.0, 5.0), subtitles=("(at beach)", None))
        msgs = [tl.message(i, ("Client", "Server")[i % 2], ("Server", "Client")[i % 2], "message %d" % i)
                for i in range(6)]
        tl.add(tl.legend())
        everything = VGroup(tl, *[p for m in msgs for p in m.parts()])
        self.assertLessEqual(everything.get_right()[0], 6.5)
        self.assertGreaterEqual(everything.get_left()[0], -6.5)
        self.assertLessEqual(everything.get_top()[1], 3.5)
        self.assertGreaterEqual(everything.get_bottom()[1], -3.5)

    def test_note_sits_outside_its_lifeline_at_the_arrival_height(self):
        tl = self.make(x=(-3, 3))
        tl.message(0, "Client", "Server", "SYN")
        right = tl.note(0, "Server", "SYN_RCVD")
        left = tl.note(0, "Client", "SYN_SENT", at="start")
        self.assertGreater(right.get_left()[0], 3)
        self.assertLess(left.get_right()[0], -3)
        self.assertAlmostEqual(right.get_center()[1], tl.y(0) - tl.slant, places=5)
        self.assertAlmostEqual(left.get_center()[1], tl.y(0), places=5)

    def test_legend_names_both_kinds(self):
        tl = self.make()
        texts = [m.original_text for m in tl.legend().get_family() if isinstance(getattr(m, "original_text", None), str)]
        self.assertIn("old duplicate", texts)
        self.assertIn("genuine", texts)

    def test_participants_are_validated(self):
        tl = self.make()
        with self.assertRaises(KeyError):
            tl.message(0, "Client", "Nobody", "x")


class TimelineAnimationTests(_ManimTestCase):
    def test_travel_reveals_progressively_with_head_at_the_tip(self):
        import numpy as np
        from manim import linear
        from studio.cslib import Timeline
        tl = Timeline(("A", "B"), x=(-3, 3))
        m = tl.message(0, "A", "B", "data")
        anim = m.travel(run_time=2.0)
        anim.begin()
        for sub in anim.animations if hasattr(anim, "animations") else [anim]:
            sub.rate_func = linear
        anim.interpolate(0.0)
        self.assertAlmostEqual(m.head.get_fill_opacity(), 0.0)
        anim.interpolate(0.5)
        shaft = m.dashes[0]
        length = np.linalg.norm(shaft.get_end() - shaft.get_start())
        total = np.linalg.norm(m.end - m.start)
        self.assertAlmostEqual(length / total, 0.5, delta=0.08)
        ahead = np.dot(m.head_tip() - shaft.get_end(), m.direction)
        self.assertGreater(ahead, 0)
        self.assertLess(ahead, m.HEAD)
        anim.finish()
        np.testing.assert_allclose(m.head_tip(), m.end, atol=1e-6)
        self.assertAlmostEqual(m.head.get_fill_opacity(), 1.0)

    def test_staged_travel_resumes_where_it_stopped(self):
        import numpy as np
        from studio.cslib import Timeline
        tl = Timeline(("A", "B"), x=(-3, 3))
        m = tl.message(0, "A", "B", "data")
        first = m.travel(run_time=1.0, upto=0.6)
        first.begin(); first.finish()
        mid = m.head_tip().copy()
        np.testing.assert_allclose(mid, m.start + 0.6 * (m.end - m.start), atol=1e-6)
        second = m.travel(run_time=1.0, start=0.6, label=False)
        second.begin(); second.interpolate(0.0)
        np.testing.assert_allclose(m.head_tip(), mid, atol=1e-6)
        second.finish()
        np.testing.assert_allclose(m.head_tip(), m.end, atol=1e-6)

    def test_dashed_travel_hides_dashes_beyond_the_tip(self):
        from manim import linear
        from studio.cslib import Timeline
        tl = Timeline(("A", "B"), x=(-3, 3))
        m = tl.message(0, "A", "B", "old", kind="old")
        anim = m.travel(run_time=1.0, label=False)
        anim.begin()
        anim.rate_func = linear
        anim.interpolate(0.3)
        visible = [d for d in m.dashes if d.get_stroke_opacity() > 0]
        self.assertLess(len(visible), len(m.dashes))
        self.assertGreater(len(visible), 0)

    def test_relabel_cross_fades_in_place_keeping_identity(self):
        import numpy as np
        from studio.cslib import Timeline
        tl = Timeline(("A", "B"))
        m = tl.message(0, "A", "B", "Data 2")
        label_id = id(m.label)
        center = m.label.get_center().copy()
        anim = m.relabel("Data 2 (resent)")
        anim.begin(); anim.finish()
        self.assertEqual(id(m.label), label_id)
        self.assertAlmostEqual(m.label.get_center()[1], center[1], places=5)
        self.assertGreater(m.label[0].get_fill_opacity(), 0.99)


class HelperTests(_ManimTestCase):
    def test_cross_fade_becomes_new_text_without_morphing(self):
        import numpy as np
        from manim import Text, linear
        from studio.cslib import cross_fade
        old, new = Text("before"), Text("after, longer").shift(np.array([1.0, 0, 0]))
        anim = cross_fade(old, new, run_time=1.0)
        anim.rate_func = linear
        anim.begin()
        anim.interpolate(0.25)
        self.assertLess(old.get_fill_opacity(), 0.6)
        anim.interpolate(0.75)
        np.testing.assert_allclose(old.get_center(), new.get_center(), atol=1e-6)
        anim.finish()
        self.assertEqual(len(old.submobjects), len(new.submobjects))
        self.assertAlmostEqual(old.get_fill_opacity(), 1.0)
        self.assertEqual(old.original_text, "after, longer")
        self.assertAlmostEqual(old.font_size, new.font_size, places=3)  # reviewer reads this

    def test_source_tag_set_cross_fades_instead_of_transform(self):
        from manim import Transform
        from studio.cslib import SourceTag
        tag = SourceTag("Deck · slide 4")
        anim = tag.set("Added example · based on slide 4")
        self.assertNotIsInstance(anim, Transform)
        anim.begin(); anim.finish()
        self.assertEqual(len(tag.submobjects), 1)

    def test_beat_time_uses_bookmark_or_remainder_with_a_floor(self):
        from studio.cslib import beat
        t = FakeTracker(remaining=3.2, marks={"go": 1.5, "now": 0.0})
        self.assertAlmostEqual(beat(t), 3.2)
        self.assertAlmostEqual(beat(t, "go"), 1.5)
        self.assertAlmostEqual(beat(t, "now"), 0.3)
        self.assertAlmostEqual(beat(t, "now", floor=0.1), 0.1)


class SceneWaitTests(unittest.TestCase):
    def test_wait_for_skips_tiny_gaps_and_waits_otherwise(self):
        from studio.base import StudyScene

        class Probe:
            waits = []

            def wait(self, d):
                self.waits.append(d)

        probe = Probe()
        StudyScene.wait_for(probe, FakeTracker(remaining=0.02))
        StudyScene.wait_for(probe, FakeTracker(remaining=1.25))
        StudyScene.wait_for(probe, FakeTracker(marks={"x": 0.8}), "x")
        self.assertEqual(probe.waits, [1.25, 0.8])


if __name__ == "__main__":
    unittest.main()
