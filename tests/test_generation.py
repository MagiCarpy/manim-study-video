"""Shared maintenance regressions; run with bin/study python -m unittest discover
-s tests -p 'test_generation.py' -v.
No narration synthesis, lesson writes, or external services.
"""
import unittest

from studio.review import parse_script


class ScriptBeatsTests(unittest.TestCase):
    def test_beat_suffix_is_metadata_not_multiline_speech(self):
        script = """## First
[01] The first sentence.
    Legitimate indented speech continues here. [pause]
And a final spoken line.
  beats: show the table;
    pulse the first row
    - reveal a value

    finish the annotation after a blank line.
[02] Next block.
beats:
- reveal the next object
  then move it
## Second
[01] Last spoken line.
beats: hide everything
"""
        self.assertEqual(parse_script(script), {
            "First": [[1, "The first sentence. Legitimate indented speech continues here. [pause] And a final spoken line."],
                      [2, "Next block."]],
            "Second": [[1, "Last spoken line."]],
        })

    def test_ordinary_multiline_speech_without_annotations(self):
        self.assertEqual(parse_script("## Talk\n[03] A sentence.\n\n  Another spoken sentence.\nA beats: word inside speech."),
                         {"Talk": [[3, "A sentence. Another spoken sentence. A beats: word inside speech."]]})


class ScriptLintIntegrationTests(unittest.TestCase):
    def test_beats_do_not_mask_real_narration_drift(self):
        import os
        from pathlib import Path
        import tempfile
        from studio.review import script_lint
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as directory:
            folder = Path(directory)
            (folder / "script.md").write_text("## Talk\n[01] First speech.\n  More speech.\n  beats:\n    - reveal a table\n    - pulse a row\n")
            scene = "class Talk:\n    def construct(self):\n        self.voiceover(text='First speech. More speech.')\n"
            (folder / "scenes.py").write_text(scene)
            self.assertEqual(script_lint(folder), [])
            (folder / "scenes.py").write_text(scene.replace("More speech.", "Changed speech."))
            self.assertEqual([i["code"] for i in script_lint(folder)], ["script_mismatch"])


class LintPolicyGuardTests(unittest.TestCase):
    def test_short_four_sentence_blocks_still_error_without_policy_change(self):
        import os
        from pathlib import Path
        import tempfile
        from studio.review import static_lint
        text22 = "Mallory can do three things. She can read your messages. She can change them. And she can claim to be someone else."
        text25 = text22.replace("else.", "else without being detected.")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as directory:
            folder = Path(directory)
            for words, text in ((22, text22), (25, text25)):
                with self.subTest(words=words):
                    self.assertEqual(len(text.split()), words)
                    (folder / "scenes.py").write_text(f"class Talk:\n    def construct(self):\n        self.voiceover(text={text!r})\n")
                    found = [i for i in static_lint(folder, {"scenes": [{"name": "Talk"}]})
                             if i["code"] == "long_voiceover"]
                    self.assertEqual(len(found), 1)
                    self.assertEqual(found[0]["severity"], "error")
                    self.assertEqual(found[0]["message"], f"Voiceover has {words} words / 4 sentences")


class _ManimTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        import tempfile
        import studio
        from manim import tempconfig
        media = cls.enterClassContext(tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")))
        cls.enterClassContext(tempconfig({"media_dir": media}))


class PulseTests(_ManimTestCase):
    def test_table_row_keeps_independent_fill_and_stroke_at_every_alpha(self):
        import numpy as np
        import studio  # Install the local SoX stub before importing Manim.
        from manim import ManimColor, linear
        from studio import style
        from studio.cslib import MemoryTable, pulse

        table = MemoryTable([["zero", "one"]], headers=["left", "right"])
        row = table.grid[1]
        rects = [cell[0] for cell in row]
        labels = [cell[1] for cell in row]
        # Mixed opacity, width and z-order must survive emphasis too.
        rects[0].set_fill(style.BLUE, opacity=.4).set_stroke(style.RED, width=1, opacity=.6)
        rects[1].set_stroke(style.TEAL, width=3)
        labels[1].set_z_index(2)
        family = table.get_family()
        identities = [(id(m), tuple(map(id, m.submobjects)), m.z_index) for m in family]
        before = {id(m): m.copy() for m in family}
        animation = pulse(row, color=style.YELLOW)
        animation.rate_func = linear
        self.assertIs(animation.mobject, row)
        animation.begin()
        for alpha in (0, .25, .5, .75, 1):
            animation.interpolate(alpha)
            self.assertEqual([(id(m), tuple(map(id, m.submobjects)), m.z_index) for m in table.get_family()], identities)
            for m in row.get_family():
                old = before[id(m)]
                np.testing.assert_array_equal(m.fill_rgbas, old.fill_rgbas)
                np.testing.assert_array_equal(m.stroke_rgbas[:, 3], old.stroke_rgbas[:, 3])
                if m not in rects or alpha in (0, 1):
                    np.testing.assert_array_equal(m.stroke_rgbas, old.stroke_rgbas)
                    self.assertEqual(m.stroke_width, old.stroke_width)
            if alpha == .5:
                for rect in rects:
                    np.testing.assert_allclose(rect.get_stroke_color().to_rgb(), ManimColor(style.YELLOW).to_rgb())
                    self.assertEqual(rect.get_stroke_width(), before[id(rect)].get_stroke_width() + 3)
        animation.finish()
        for m in family:
            np.testing.assert_array_equal(m.points, before[id(m)].points)
            np.testing.assert_array_equal(m.fill_rgbas, before[id(m)].fill_rgbas)
            np.testing.assert_array_equal(m.stroke_rgbas, before[id(m)].stroke_rgbas)


class TableIndexTests(_ManimTestCase):
    def test_data_row_zero_excludes_headers_and_documentation_agrees(self):
        import studio
        from pathlib import Path
        from studio import review
        from studio.cslib import MemoryTable, PrefixTable
        for table in (MemoryTable([["first", "data"]], headers=["a", "b"]),
                      MemoryTable([["first", "data"]]),
                      PrefixTable([("10*", "first"), ("*", "default")])):
            with self.subTest(table=type(table).__name__, header=table.has_header):
                row = table.grid[1 if table.has_header else 0]
                self.assertIs(table.cell(0, 0), row[0])
                self.assertEqual([a.mobject for a in table.highlight_row(0).animations],
                                 [cell[0] for cell in row])
        card = (review.SKILL_DIR / "references" / "worker-card.md").read_text()
        self.assertIn("first data row = 0", card)
        self.assertNotIn("row indexes include the header row", card)


if __name__ == "__main__":
    unittest.main()
