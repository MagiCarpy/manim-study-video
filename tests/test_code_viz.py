"""Code-visualization helpers: ASTTree, CodeListing, ScopeStack (programming-language lectures)."""
import tempfile
import unittest
from pathlib import Path

from tests.test_generation import _ManimTestCase


def hexof(c):
    return c.to_hex().lower()


def _overlap(a, b, eps=1e-6):
    return not (a.get_right()[0] <= b.get_left()[0] + eps or b.get_right()[0] <= a.get_left()[0] + eps
                or a.get_top()[1] <= b.get_bottom()[1] + eps or b.get_top()[1] <= a.get_bottom()[1] + eps)


def _sample_tree():
    from studio.cslib import AST
    return AST("fcall",
               AST("qname", value="print", field="fn"),
               AST("fcall",
                   AST("qname", value="add2", field="fn", key="add2"),
                   AST("int", value="40", field="args", key="forty"),
                   field="args", key="inner"),
               key="call")


class ASTTreeTests(_ManimTestCase):
    def test_levels_are_ordered_and_parents_center_over_children(self):
        from studio.cslib import ASTTree
        t = ASTTree(_sample_tree())
        root, inner = t.node("call"), t.node("inner")
        add2, forty = t.node("add2"), t.node("forty")
        self.assertGreater(root.get_center()[1], inner.get_center()[1])
        self.assertGreater(inner.get_center()[1], add2.get_center()[1])
        self.assertAlmostEqual(add2.get_center()[1], forty.get_center()[1], places=5)
        mid = (add2.get_center()[0] + forty.get_center()[0]) / 2
        self.assertAlmostEqual(inner.get_center()[0], mid, places=5)
        # Path keys work too: root is (), children by index.
        self.assertIs(t.node((1, 1)), forty)
        self.assertIs(t.node(()), root)

    def test_no_box_overlaps_and_fits_frame(self):
        from studio.cslib import AST, ASTTree
        leaves = [AST("qname", value=n) for n in "abcdefg"]
        t = ASTTree(AST("fcall", AST("fcall", *leaves[:4]), AST("fcall", *leaves[4:])))
        boxes = t.boxes()
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                self.assertFalse(_overlap(boxes[i], boxes[j]), (i, j))
        self.assertLessEqual(t.width, 13.0 + 1e-6)
        self.assertLessEqual(t.height, 7.0 + 1e-6)

    def test_text_never_below_twenty_point_and_too_wide_raises(self):
        from studio.cslib import AST, ASTTree
        t = ASTTree(_sample_tree())
        for txt in t.texts():
            self.assertGreaterEqual(round(float(txt.font_size), 3), 20)
        wide = AST("fcall", *[AST("qname", value=f"name{i}") for i in range(14)])
        with self.assertRaises(ValueError):
            ASTTree(wide)

    def test_sibling_fields_share_one_label_and_labels_never_overlap(self):
        from studio.cslib import AST, ASTTree
        # Three tightly packed args siblings plus an fn sibling (as in [+ x 1]).
        t = ASTTree(AST("fcall", AST("qname", value="+", field="fn", key="f"),
                        AST("qname", value="x", field="args", key="a1"),
                        AST("int", value="1", field="args", key="a2"),
                        AST("fcall", AST("qname", value="-", field="fn"), AST("int", value="2", field="args"),
                            AST("int", value="3", field="args"), field="args", key="a3"), key="root"))
        self.assertIs(t.field_label("a1"), t.field_label("a2"))
        self.assertIs(t.field_label("a1"), t.field_label("a3"))
        labels = list(t.labels)
        self.assertEqual(len(labels), 4)  # root: fn, args; nested: fn, args
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                self.assertFalse(_overlap(a, b), (a.original_text, b.original_text))
            for box in t.boxes():
                self.assertFalse(_overlap(a, box), a.original_text)

    def test_kind_colors_and_field_labels(self):
        from studio import style
        from studio.cslib import ASTTree
        t = ASTTree(_sample_tree())
        self.assertEqual(hexof(t.node("call")[0].get_stroke_color()), hexof(style.BLUE))
        self.assertEqual(hexof(t.node("add2")[0].get_stroke_color()), hexof(style.TEAL))
        self.assertEqual(hexof(t.node("forty")[0].get_stroke_color()), hexof(style.GOLD))
        self.assertEqual(t.field_label("forty").original_text, "args")
        # Field labels never overlap each other or any node box.
        labels = [t.field_label(k) for k in ("forty", "add2", "inner")]
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                self.assertFalse(_overlap(a, b))
            for box in t.boxes():
                self.assertFalse(_overlap(a, box))
        self.assertIsNone(t.field_label("call"))
        # The edge into a node ends on that node's top edge.
        e = t.edge("forty")
        self.assertAlmostEqual(e.get_end()[1], t.node("forty")[0].get_top()[1], places=4)

    def test_visit_restores_previous_node_and_result_sits_beside(self):
        from manim import Scene
        from studio import style
        from studio.cslib import ASTTree
        t = ASTTree(_sample_tree())
        scene = Scene()
        scene.add(t)
        scene.play(t.visit("forty"), run_time=0.1)
        self.assertEqual(hexof(t.node("forty")[0].get_stroke_color()), hexof(style.YELLOW))
        # The box is never promoted above its own label (it stays inside the tree group).
        self.assertNotIn(t.node("forty")[0], scene.mobjects)
        # Each recolour animation drives the WHOLE node, so its label is redrawn above the box.
        t2 = ASTTree(_sample_tree())
        t2.visit("forty")
        anim = t2.visit("inner")
        self.assertEqual({id(a.mobject) for a in anim.animations}, {id(t2.node("inner")), id(t2.node("forty"))})
        scene.play(t.visit("add2"), run_time=0.1)
        self.assertEqual(hexof(t.node("forty")[0].get_stroke_color()), hexof(style.GOLD))
        self.assertEqual(hexof(t.node("add2")[0].get_stroke_color()), hexof(style.YELLOW))
        pill, anim = t.result("forty", "40")
        scene.play(anim, run_time=0.1)
        self.assertFalse(_overlap(pill, t.node("forty")[0]))
        scene.play(t.carry(pill, "inner"), run_time=0.1)
        self.assertFalse(_overlap(pill, t.node("inner")[0]))
        self.assertLess(abs(pill.get_center()[1] - t.node("inner").get_center()[1]), 0.6)

    def test_result_pill_avoids_field_labels(self):
        from studio.cslib import AST, ASTTree
        t = ASTTree(AST("fcall", AST("qname", value="length", field="fn"),
                        AST("list", AST("list", AST("int", value="1", field="elements"), field="elements"),
                            AST("int", value="3", field="elements"), field="args", key="outer"), key="root"))
        t.move_to([4.4, 1.3, 0])  # near the right edge: the pill must fall back to another side
        for side in (None,):
            pill_, _ = t.result("outer", "{{1 2} 3}")
            for lab in t.labels:
                self.assertFalse(_overlap(pill_, lab), lab.original_text)
            for box in t.boxes():
                self.assertFalse(_overlap(pill_, box))

    def test_grow_reveals_everything(self):
        from manim import Scene
        from studio.cslib import ASTTree
        t = ASTTree(_sample_tree())
        scene = Scene()
        scene.play(t.grow(run_time=0.3))
        self.assertTrue(all(m in scene.mobjects or any(m in s.get_family() for s in scene.mobjects)
                            for m in t.boxes()))


class CodeListingTests(_ManimTestCase):
    SRC = "\n".join([
        "class Env:",
        "    def get(self, name):",
        "        for block in reversed(self.frames[-1]):",
        "            if name in block:",
        "                return block[name]   # " + "x" * 90,
        "        return None",
    ])

    def _path(self):
        d = Path(tempfile.mkdtemp(dir=None))
        p = d / "env.py"
        p.write_text(self.SRC)
        return p

    def test_real_line_numbers_dedent_and_elision(self):
        from studio.cslib import CodeListing
        c = CodeListing(self._path(), 2, 6, max_chars=60)
        self.assertEqual(c.numbers, [2, 3, 4, 5, 6])
        self.assertTrue(c.source_text(2).startswith("def get"))  # common indent removed
        self.assertTrue(c.source_text(5).endswith("…"))
        self.assertLessEqual(len(c.source_text(5)), 60)
        self.assertEqual(c.row(3)[0].original_text.strip(), "3")
        # Indentation survives (Text drops leading-space glyphs, so the helper must offset rows).
        step = c.row(3)[1].get_left()[0] - c.row(2)[1].get_left()[0]
        self.assertAlmostEqual(step, 4 * c.char_width, delta=0.02)
        self.assertGreater(c.row(4)[1].get_left()[0], c.row(3)[1].get_left()[0] + 0.5)
        self.assertLessEqual(c.width, 13.0 + 1e-6)
        for row in c.rows:
            self.assertGreaterEqual(round(float(row[1].font_size), 3), 20)

    def test_blank_lines_and_hidden_numbers_have_no_zero_height_text(self):
        # Layout review reads Text.font_size, which divides by the glyph height: blank Text crashes it.
        from manim import Text
        from studio.cslib import CodeListing
        src = "def f():\n\n    return 1\n\n\ndef g():\n    pass"
        for kw in ({}, {"numbers": False}, {"skip": [(4, 5)]}):
            c = CodeListing(text=src, **kw)
            for m in c.get_family():
                if isinstance(m, Text):
                    self.assertGreater(m.height, 0, (kw, m.text))
                    float(m.font_size)
        c = CodeListing(text=src)
        self.assertEqual(c.numbers, [1, 2, 3, 4, 5, 6, 7])
        self.assertGreater(c.row(3).get_center()[1] - c.row(6).get_center()[1], 2.5 * c.pitch)

    def test_long_lines_elide_to_fit_max_width_instead_of_raising(self):
        from studio.cslib import CodeListing
        src = "x = " + "a" * 120 + "\ny = 1"
        c = CodeListing(text=src, max_chars=200)
        self.assertLessEqual(c.width, 13.0 + 1e-6)
        self.assertTrue(c.source_text(1).endswith("…"))
        half = CodeListing(text=src, max_width=6.5)
        self.assertLessEqual(half.width, 6.5 + 1e-6)
        self.assertEqual(half.source_text(2), "y = 1")

    def test_keywords_colored_and_skip_marker(self):
        from studio import style
        from studio.cslib import CodeListing
        c = CodeListing(self._path(), 2, 6, skip=[(4, 5)])
        self.assertEqual(c.numbers, [2, 3, 6])
        self.assertTrue(any(getattr(r, "is_skip", False) for r in c.rows))
        # 'def' keyword is coloured differently from the identifier 'get'.
        line = c.row(2)[1]
        colors = {hexof(ch.get_fill_color()) for ch in line}
        self.assertIn(hexof(style.PURPLE), colors)
        self.assertIn(hexof(style.FG), colors)

    def test_highlight_moves_one_bar(self):
        from manim import Scene
        from studio.cslib import CodeListing
        c = CodeListing(self._path(), 1, 6)
        scene = Scene(); scene.add(c)
        scene.play(c.highlight(3), run_time=0.1)
        bar = c.bar
        self.assertLess(abs(bar.get_center()[1] - c.row(3).get_center()[1]), 0.05)
        scene.play(c.highlight(4, 5), run_time=0.1)
        self.assertIs(c.bar, bar)
        mid = (c.row(4).get_center()[1] + c.row(5).get_center()[1]) / 2
        self.assertLess(abs(bar.get_center()[1] - mid), 0.05)
        self.assertGreaterEqual(bar.height, c.row(4).get_top()[1] - c.row(5).get_bottom()[1] - 1e-6)

    def test_from_text_brewin_and_too_many_lines(self):
        from studio import style
        from studio.cslib import CodeListing
        c = CodeListing.from_text('[func main []\n  [print "hi" 42]]', language="brewin", numbers=False)
        self.assertEqual(len(c.rows), 2)
        colors = {hexof(ch.get_fill_color()) for ch in c.row(1)[1]}
        self.assertIn(hexof(style.PURPLE), colors)  # func keyword
        colors2 = {hexof(ch.get_fill_color()) for ch in c.row(2)[1]}
        self.assertIn(hexof(style.GOLD), colors2)  # string / number literal
        with self.assertRaises(ValueError):
            CodeListing.from_text("\n".join(f"x{i}" for i in range(40)))


    def test_required_lines_cannot_be_silently_elided_or_skipped(self):
        from studio.cslib import CodeListing
        src = 'kept\n' + 'x' * 100 + '\nlast'
        self.assertEqual(CodeListing(text=src, required_lines=[1]).source_text(1), 'kept')
        with self.assertRaisesRegex(ValueError, 'Required code line 2.*elided'):
            CodeListing(text=src, max_width=6, required_lines=[2])
        with self.assertRaisesRegex(ValueError, 'Required code line 2.*not displayed'):
            CodeListing(text=src, skip=[(2, 2)], required_lines=[2])

    def test_named_content_regions_require_a_gutter(self):
        from manim import Rectangle
        from studio.cslib import check_regions
        listing = Rectangle(width=2, height=1)
        panel = Rectangle(width=2, height=1).shift([2.05, 0, 0])
        with self.assertRaisesRegex(ValueError, 'listing.*panel'):
            check_regions(listing=listing, panel=panel)
        panel.shift([.2, 0, 0])
        check_regions(listing=listing, panel=panel)


class ScopeStackTests(_ManimTestCase):
    def test_frames_blocks_define_and_lookup(self):
        from manim import Scene
        from studio.cslib import ScopeStack
        env = ScopeStack(x=4, bottom=-3.2, width=4.2)
        scene = Scene(); scene.add(env)
        scene.play(env.push_frame("main"), run_time=0.1)
        scene.play(env.define("x", "5"), run_time=0.1)
        scene.play(env.push_block(), run_time=0.1)
        scene.play(env.define("x", "6"), run_time=0.1)
        self.assertEqual(env.state(), [[[("x", "5")], [("x", "6")]]])
        anim, found = env.lookup("x")
        self.assertEqual(found, (0, 1, 0))  # frame 0, innermost block 1, row 0
        scene.play(anim, run_time=0.2)
        # Innermost block sits above the outer one.
        self.assertGreater(env.block(0, 1).get_center()[1], env.block(0, 0).get_center()[1])
        scene.play(env.pop_block(), run_time=0.1)
        self.assertEqual(env.state(), [[[("x", "5")]]])

    def test_compact_fits_five_frames_above_the_source_tag(self):
        from manim import Scene
        from studio.cslib import ScopeStack, SourceTag
        tag = SourceTag("interpreterv3.py · lines 328–341 · notes §1")
        env = ScopeStack(x=4.4, bottom=tag.get_top()[1] + 0.15, width=3.8, compact=True)
        scene = Scene(); scene.add(env)
        for name in ["main", "sumdown", "sumdown", "sumdown", "sumdown"]:
            scene.play(env.push_frame(name), run_time=0.05)
            scene.play(env.define("n", "3"), run_time=0.05)
        self.assertLessEqual(env.get_top()[1], 3.5 + 1e-6)
        self.assertFalse(_overlap(env, tag))
        self.assertGreaterEqual(min(round(float(t.font_size), 3) for t in env.get_family()
                                    if hasattr(t, "font_size") and t.height > 0), 20)

    def test_new_frame_hides_caller_names_and_custom_blocks(self):
        from manim import Scene
        from studio.cslib import ScopeStack
        env = ScopeStack(x=4, bottom=-3.2, width=4.2)
        scene = Scene(); scene.add(env)
        scene.play(env.push_frame("main"), run_time=0.1)
        scene.play(env.define("x", "99"), run_time=0.1)
        scene.play(env.push_frame("λ call", blocks=[[("x", "10")], [("y", "4")]]), run_time=0.1)
        self.assertEqual(len(env.state()), 2)
        anim, found = env.lookup("y")
        self.assertEqual(found, (1, 1, 0))
        anim, found = env.lookup("missing")
        self.assertIsNone(found)
        scene.play(anim, run_time=0.2)
        # The new frame is drawn above the caller and everything stays inside the frame area.
        self.assertGreater(env.frame(1).get_center()[1], env.frame(0).get_center()[1])
        self.assertLessEqual(env.get_top()[1], 3.5 + 1e-6)
        scene.play(env.pop_frame(), run_time=0.1)
        self.assertEqual(env.state(), [[[("x", "99")]]])


if __name__ == "__main__":
    unittest.main()
