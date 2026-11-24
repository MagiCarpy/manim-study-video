"""Layout primitives every section used to re-implement (T, P, panel, card, host, pill, arrows...)."""
import unittest

from tests.test_generation import _ManimTestCase


def hexof(c):
    return c.to_hex().lower()


class PrimitiveTests(_ManimTestCase):
    def test_point_and_panel(self):
        import numpy as np
        from studio import style
        from studio.cslib import P, panel
        np.testing.assert_allclose(P(1.5, -2), [1.5, -2.0, 0.0])
        p = panel(3, 1.2)
        self.assertAlmostEqual(p.width, 3, places=3)
        self.assertEqual(hexof(p.get_fill_color()), hexof(style.PANEL))
        self.assertEqual(hexof(p.get_stroke_color()), hexof(style.DIM))

    def test_boxed_grows_to_fit_instead_of_shrinking_text(self):
        from studio.cslib import boxed, label
        b = boxed("a rather long label for a small box", 1.0, 0.6, size=22)
        rect, text = b
        self.assertAlmostEqual(text.height, label("a rather long label for a small box", size=22).height, places=4)
        self.assertGreaterEqual(rect.width, text.width + 0.2)
        np_center = rect.get_center() - text.get_center()
        self.assertLess(abs(np_center[0]) + abs(np_center[1]), 1e-6)
        self.assertAlmostEqual(boxed("ok", 2.0, 0.6)[0].width, 2.0, places=3)

    def test_card_wraps_to_width_with_no_orphan_word(self):
        from studio.cslib import card
        c = card("Ports name the process inside a host so one machine can run many conversations at once", 5.0, size=24)
        rect, lines = c
        self.assertAlmostEqual(rect.width, 5.0, places=3)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(line.width, 5.0 - 0.4 + 1e-6)
        self.assertGreater(len(lines[-1].original_text.split()), 1)
        self.assertGreaterEqual(rect.height, lines.height + 0.3)

    def test_host_pill_mark_text_at(self):
        import numpy as np
        from manim import LEFT, RIGHT
        from studio import style
        from studio.cslib import host, mark, pill, text_at
        h = host("Client", "10.0.0.1:5000", style.BLUE)
        self.assertEqual(len(h), 3)
        self.assertEqual(hexof(h[1].get_color()), hexof(style.BLUE))
        self.assertEqual(len(host("Server")), 2)
        p = pill("SYN", style.GOLD)
        self.assertGreater(p[0].width, p[1].width)
        self.assertEqual(mark(True).original_text, "✓")
        self.assertEqual(hexof(mark(False).get_color()), hexof(style.RED))
        t = text_at("left edge", -2, 1)
        self.assertAlmostEqual(t.get_left()[0], -2, places=5)
        r = text_at("right edge", 2, 1, align=RIGHT)
        self.assertAlmostEqual(r.get_right()[0], 2, places=5)

    def test_arrow_tip_lands_on_target_with_fixed_head_size(self):
        import numpy as np
        from studio.cslib import arrow
        short = arrow((0, 0, 0), (1, 0, 0))
        long = arrow((0, 0, 0), (8, 0, 0))
        self.assertAlmostEqual(short.head.get_right()[0], 1.0, places=5)
        self.assertAlmostEqual(short.head.width, long.head.width, places=5)
        both = arrow((0, 0, 0), (3, 0, 0), both=True)
        self.assertAlmostEqual(both.tail_head.get_left()[0], 0.0, places=5)
        dashed = arrow((0, 0, 0), (4, 0, 0), dashed=True)
        self.assertGreater(len(dashed.shaft.submobjects), 3)

    def test_bracket_ticks_point_back_toward_the_line(self):
        from manim import LEFT, RIGHT
        from studio.cslib import bracket
        left = bracket(0, 1, -1, side=LEFT)
        self.assertAlmostEqual(left.get_right()[0], 0.15, places=5)
        self.assertAlmostEqual(left.get_left()[0], 0.0, places=5)
        right = bracket(0, 1, -1, side=RIGHT)
        self.assertAlmostEqual(right.get_left()[0], -0.15, places=5)

    def test_rich_text_is_one_text_coloured_by_part(self):
        from studio import style
        from studio.cslib import rich_text
        t = rich_text([("SYN", style.GOLD), ("seq 1000", style.FG)])
        self.assertEqual(t.original_text, "SYN seq 1000")
        self.assertEqual(hexof(t.submobjects[0].get_color()), hexof(style.GOLD))
        self.assertEqual(rich_text("plain").original_text, "plain")

    def test_later_and_appear(self):
        from manim import FadeIn, Square
        from studio.cslib import appear, later
        s = Square()
        self.assertAlmostEqual(later(0.5, FadeIn(s, run_time=1)).run_time, 1.5, places=5)
        self.assertAlmostEqual(later(0.0, FadeIn(s, run_time=1)).run_time, 1.0, places=5)
        a = appear(s, run_time=0.2)
        self.assertAlmostEqual(s.get_fill_opacity(), 0.0)

    def test_text_below_twenty_is_refused(self):
        from studio.cslib import boxed, card, pill, text_at
        for make in (lambda: boxed("x", 1, 1, size=18), lambda: card("x y", 3, size=16),
                     lambda: pill("x", size=19), lambda: text_at("x", 0, 0, size=12)):
            with self.assertRaises(ValueError):
                make()


if __name__ == "__main__":
    unittest.main()
