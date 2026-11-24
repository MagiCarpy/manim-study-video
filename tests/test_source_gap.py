"""Text that touches the source tag without overlapping it still reads as one label."""
import unittest

from studio.review import layout_issues

TAG = dict(text="CS 118 · slide 35", bbox=[3.0, -3.45, 6.4, -3.15], font_size=20, source=True)


def box(bbox, text="TCP default: at least 2 hours idle"):
    return dict(text=text, bbox=bbox, font_size=22, source=False)


def codes(boxes):
    return [i["code"] for i in layout_issues(boxes)]


class SourceGapTests(unittest.TestCase):
    def test_text_abutting_the_tag_warns(self):
        found = layout_issues([TAG, box([2.0, -3.12, 5.0, -2.8])])   # 0.03 above the tag
        gap = [i for i in found if i["code"] == "source_tag_gap"]
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0]["severity"], "warning")
        self.assertIn("TCP default", gap[0]["texts"][1])

    def test_text_beside_the_tag_warns(self):
        self.assertIn("source_tag_gap", codes([TAG, box([1.5, -3.4, 2.95, -3.2])]))   # 0.05 left

    def test_clear_text_and_other_pairs_do_not_warn(self):
        self.assertNotIn("source_tag_gap", codes([TAG, box([2.0, -2.9, 5.0, -2.6])]))  # 0.25 above
        self.assertNotIn("source_tag_gap", codes([box([0, 0, 1, 0.3], "a"), box([0, 0.32, 1, 0.6], "b")]))
        self.assertNotIn("source_tag_gap", codes([TAG, box([-5, -3.4, -3, -3.2])]))     # far left


if __name__ == "__main__":
    unittest.main()
