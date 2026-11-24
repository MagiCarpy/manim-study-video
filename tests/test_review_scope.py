"""`study review --scene`: check only the named scenes (work orders run before later scenes exist)."""
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import yaml

from studio import review

SCENES = textwrap.dedent("""\
    from studio.base import StudyScene
    from studio.cslib import source_tag
    class A(StudyScene):
        def construct(self):
            self.add(source_tag("Deck · slide 1"))
    """)


class ReviewScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.f = Path(self.tmp.name)
        (self.f / "lesson.yaml").write_text(yaml.safe_dump({"title": "T", "scenes": [{"name": "A"}, {"name": "B"}]}))
        (self.f / "scenes.py").write_text(SCENES)

    def tearDown(self):
        self.tmp.cleanup()

    def codes(self):
        import json
        return [i["code"] for i in json.loads((self.f / "build" / "review" / "report.json").read_text())["issues"]
                if i["severity"] == "error"]

    def test_lint_scoped_to_scene_ignores_scenes_not_yet_written(self):
        review.main([str(self.f), "--lint"])
        self.assertIn("missing_scene", self.codes())
        self.assertEqual(review.main([str(self.f), "--lint", "--scene", "A"]), 0)
        self.assertNotIn("missing_scene", self.codes())

    def test_targeted_review_reports_only_requested_script(self):
        (self.f / 'script.md').write_text('## A\n[01] First\n## B\n[01] Later\n')
        review.main([str(self.f), '--lint', '--scene', 'A'])
        import json
        issues = json.loads((self.f / 'build/review/report.json').read_text())['issues']
        self.assertEqual([(i['code'], i.get('scene')) for i in issues], [('script_mismatch', 'A')])

    def test_unknown_scene_is_an_error(self):
        self.assertNotEqual(review.main([str(self.f), "--lint", "--scene", "Nope"]), 0)

    def test_scoped_layout_reuses_a_matching_record_and_rejects_changed_source(self):
        from studio.build import scene_paths
        spec = yaml.safe_load((self.f / 'lesson.yaml').read_text())
        video, _ = scene_paths(self.f, 'A', 'l')
        video.parent.mkdir(parents=True)
        video.write_bytes(b'clip')
        asset = self.f / 'source' / 'diagram.svg'
        asset.parent.mkdir()
        asset.write_text('before')
        out = self.f / 'build/review'
        out.mkdir(parents=True)
        (out / 'layout.A.jsonl').write_text('{"scene":"A","issues":[]}\n')
        with mock.patch.object(review.subprocess, 'run') as render:
            self.assertTrue(review.record_layout(self.f, spec, review.fingerprint(self.f), 'say', scenes=['A']))
            _, rows, timing = review.layout_review(self.f, spec, out, [], 'o', scenes=['A'])
            self.assertTrue(timing['reused'])
            self.assertEqual([r['scene'] for r in rows], ['A'])
            render.assert_not_called()
        self.assertFalse(review.layout_reusable(self.f, spec))  # B was never rendered
        asset.write_text('after')
        self.assertFalse(review.layout_reusable(self.f, spec, scenes=['A']))

    def test_scoped_layout_builds_only_those_scenes_and_reads_their_snapshots(self):
        calls = []
        def fake_run(cmd, **kw):
            calls.append(cmd)
            out = self.f / "build" / "review"
            out.mkdir(parents=True, exist_ok=True)
            (out / "layout.A.jsonl").write_text('{"scene": "A", "time": 1.0, "narration": null, "issues": [], "boxes": []}\n')
            from studio.build import scene_paths
            video, _ = scene_paths(self.f, 'A', 'l')
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_bytes(b'clip')
            review.record_layout(self.f, spec, review.fingerprint(self.f), 'say', scenes=['A'])
            return mock.Mock(returncode=0, stdout="", stderr="")
        spec = yaml.safe_load((self.f / "lesson.yaml").read_text())
        with mock.patch.object(review.subprocess, "run", fake_run):
            found, rows, timing = review.layout_review(self.f, spec, self.f / "build" / "review", [], "o", scenes=["A"])
        self.assertEqual(found, [])
        self.assertEqual([r["scene"] for r in rows], ["A"])
        cmd = calls[0]
        self.assertIn("--scene", cmd)
        self.assertEqual(cmd[cmd.index("--scene") + 1], "A")
        self.assertIn("--review", cmd)


if __name__ == "__main__":
    unittest.main()
