"""Lint that keeps animation lean: no re-implemented library helpers, no unexplained decorative motion."""
import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from studio.review import static_lint


def lint(code):
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
        folder = Path(d)
        (folder / "scenes.py").write_text(textwrap.dedent(code))
        return static_lint(folder, {"scenes": [{"name": "S"}]})


def codes(found, code):
    return [f for f in found if f["code"] == code]


HEAD = """\
from studio.base import StudyScene
from studio.cslib import source_tag
class S(StudyScene):
    def construct(self):
        self.add(source_tag("Deck · slide 1"))
"""


class RedefinedHelperTests(unittest.TestCase):
    def test_local_copies_of_library_helpers_warn_with_the_replacement(self):
        found = lint(textwrap.dedent("""\
            def T(text, size=24):
                return text
            def panel(w, h):
                return None
            class TL:
                pass
            def wait_to(scene, t, mark):
                pass
            def lifeline_glow():
                pass
            """) + HEAD)
        hits = {f["name"]: f for f in codes(found, "redefined_helper")}
        self.assertEqual(set(hits), {"T", "panel", "TL", "wait_to"})
        self.assertIn("label", hits["T"]["message"])
        self.assertIn("Timeline", hits["TL"]["message"])
        self.assertIn("wait_for", hits["wait_to"]["message"])
        self.assertTrue(all(f["severity"] == "warning" for f in hits.values()))


class MotionPolicyTests(unittest.TestCase):
    def test_decorative_motion_warns_unless_it_names_its_concept(self):
        found = lint(HEAD + """\
        dial = None
        self.play(Rotate(dial, angle=3))
        self.play(MoveAlongPath(dial, path))
        # concept: the segment's travel time is the RTT being explained
        self.play(packet_flight(pkt, a, b))
        self.play(packet_route(pkt, pts))  # concept: the path through the routers is the lesson
        dial.add_updater(lambda m: m)
        self.play(Wiggle(dial))
""")
        hits = codes(found, "decorative_motion")
        self.assertEqual(sorted(f["call"] for f in hits), ["MoveAlongPath", "Rotate", "Wiggle", "add_updater"])
        self.assertTrue(all(f["severity"] == "warning" for f in hits))

    def test_static_emphasis_helpers_are_not_flagged(self):
        found = lint(HEAD + """\
        self.play(flow_flash(link), focus([a], self.mobjects), FadeIn(x))
        self.play(syn.travel(run_time=1))
""")
        self.assertEqual(codes(found, "decorative_motion"), [])


if __name__ == "__main__":
    unittest.main()
