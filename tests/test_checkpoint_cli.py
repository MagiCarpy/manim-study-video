"""`study checkpoint`: safe, atomic checkpoint.yaml updates for headless workers (no python -c / heredocs)."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from studio import checkpoint as ck


class CheckpointCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.s = Path(self.tmp.name)
        (self.s / "checkpoint.yaml").write_text(yaml.safe_dump({
            "section_id": "05", "state": "frozen", "completed": ["notes", "storyboard", "script"],
            "input_fingerprint": {"files": {"script.md": "abc"}, "combined_sha256": "old"},
            "roles": {"planner": "opus"}, "stage_runs": [{"stage": "plan"}]}))
        (self.s / "scenes.py").write_text("class A: pass\n")
        (self.s / "script.md").write_text("x")

    def tearDown(self):
        self.tmp.cleanup()

    def data(self):
        return yaml.safe_load((self.s / "checkpoint.yaml").read_text())

    def test_freeze_waits_for_all_planning_artifacts(self):
        (self.s / 'checkpoint.yaml').write_text('state: planned\n')
        (self.s / 'lesson.yaml').write_text('scenes: [{name: A, storyboard: Show one step}]\n')
        (self.s / 'notes.md').write_text('Verified trace\n')
        self.assertNotEqual(ck.main([str(self.s), '--freeze']), 0)
        self.assertEqual(self.data()['state'], 'planned')
        (self.s / 'script.md').write_text('## A\n[01] One step.\nbeats: Reveal it.\n')
        self.assertEqual(ck.main([str(self.s), '--freeze']), 0)
        self.assertEqual(self.data()['state'], 'frozen')
        self.assertEqual(set(self.data()['completed']), {'notes', 'storyboard', 'script'})

    def test_scene_progress_merges_and_keeps_other_keys(self):
        self.assertEqual(ck.main([str(self.s), "--scene", "A", "--say-draft", "built", "--layout", "passed"]), 0)
        ck.main([str(self.s), "--scene", "B", "--say-draft", "built", "--layout", "issues",
                 "--last-error", "B: label overlaps at 3.2 s"])
        d = self.data()
        self.assertEqual(d["scene_progress"]["A"], {"say_draft": "built", "layout_review": "passed"})
        self.assertEqual(d["scene_progress"]["B"]["layout_review"], "issues")
        self.assertEqual(d["last_error"], "B: label overlaps at 3.2 s")
        self.assertEqual(d["roles"], {"planner": "opus"})
        self.assertEqual(d["state"], "frozen")
        ck.main([str(self.s), "--clear-error"])
        self.assertIsNone(self.data()["last_error"])

    def test_proposed_speech_edits_append(self):
        ck.main([str(self.s), "--propose-edit", "A [02]: say 'eight thousand and one'"])
        ck.main([str(self.s), "--propose-edit", "B [01]: split at the pause"])
        self.assertEqual(len(self.data()["proposed_speech_edits"]), 2)

    def test_hold_records_a_justified_static_hold(self):
        ck.main([str(self.s), "--hold", "FinHandshake [04]: reading hold on the state table"])
        self.assertEqual(self.data()["justified_static_holds"], ["FinHandshake [04]: reading hold on the state table"])
        self.assertNotEqual(ck.main([str(self.s), "--hold", "no scene block prefix"]), 0)

    def test_hold_must_name_a_real_scene(self):
        (self.s / "lesson.yaml").write_text(yaml.safe_dump({"scenes": [{"name": "FinHandshake"}]}))
        self.assertNotEqual(ck.main([str(self.s), "--hold", "Scene [08]: final recap"]), 0)
        self.assertEqual(ck.main([str(self.s), "--hold", "FinHandshake [08]: final recap"]), 0)

    def test_draft_marks_state_fingerprint_and_stage_run(self):
        ck.main([str(self.s), "--draft", "--model", "claude-sonnet-5-5", "--outcome", "3 scenes, PASS"])
        d = self.data()
        self.assertEqual(d["state"], "draft")
        self.assertEqual(d["completed"], ["notes", "storyboard", "script", "code", "draft_review"])
        want = hashlib.sha256(b"class A: pass\n").hexdigest()
        self.assertEqual(d["input_fingerprint"]["files"]["scenes.py"], want)
        files = d["input_fingerprint"]["files"]
        combined = hashlib.sha256("\n".join(f"{k}:{files[k]}" for k in sorted(files)).encode()).hexdigest()
        self.assertEqual(d["input_fingerprint"]["combined_sha256"], combined)
        self.assertEqual(d["stage_runs"][-1]["stage"], "animate+draft")
        self.assertEqual(d["stage_runs"][-1]["model"], "claude-sonnet-5-5")
        self.assertIn("narrate", d["next_action"])

    def test_flat_fingerprint_format_is_respected(self):
        d = self.data(); d["input_fingerprint"] = {"script.md": "abc"}
        (self.s / "checkpoint.yaml").write_text(yaml.safe_dump(d))
        ck.main([str(self.s), "--draft", "--model", "m", "--outcome", "ok"])
        self.assertIn("scenes.py", self.data()["input_fingerprint"])

    def test_scalar_fingerprint_is_kept_as_combined_and_files_added(self):
        # A planner may record one combined hash string; --draft must not crash on it.
        d = self.data(); d["input_fingerprint"] = "deadbeef"
        (self.s / "checkpoint.yaml").write_text(yaml.safe_dump(d))
        self.assertEqual(ck.main([str(self.s), "--draft", "--model", "m", "--outcome", "ok"]), 0)
        fp = self.data()["input_fingerprint"]
        self.assertEqual(fp["previous_combined_sha256"], "deadbeef")
        self.assertIn("scenes.py", fp["files"])
        self.assertEqual(self.data()["state"], "draft")

    def test_file_mode_is_preserved(self):
        os.chmod(self.s / "checkpoint.yaml", 0o644)
        ck.main([str(self.s), "--clear-error"])
        self.assertEqual((self.s / "checkpoint.yaml").stat().st_mode & 0o777, 0o644)

    def test_invalid_values_are_refused_and_file_untouched(self):
        before = (self.s / "checkpoint.yaml").read_text()
        self.assertNotEqual(ck.main([str(self.s), "--scene", "A", "--layout", "great"]), 0)
        self.assertNotEqual(ck.main([str(self.s), "--say-draft", "built"]), 0)   # needs --scene
        self.assertEqual((self.s / "checkpoint.yaml").read_text(), before)


if __name__ == "__main__":
    unittest.main()
