"""The distributed source-only example must satisfy generation lint."""
from pathlib import Path
import unittest
import yaml
from studio.paths import SKILL_DIR
from studio.review import script_lint, static_lint

class ExampleTests(unittest.TestCase):
    def test_hello_speech_and_source_labels_are_valid(self):
        lesson=SKILL_DIR/'examples/hello'
        spec=yaml.safe_load((lesson/'lesson.yaml').read_text())
        findings=static_lint(lesson,spec)+script_lint(lesson)
        # Source examples intentionally do not distribute generated caption/transcript files.
        unexpected=[item for item in findings if not (item['code']=='missing_sidecar' and item['severity']=='warning')]
        self.assertEqual(unexpected,[])

if __name__=='__main__':unittest.main()
