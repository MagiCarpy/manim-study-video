"""Release-facing commands must preserve pinned models and portable paths."""
import re
import unittest
from unittest.mock import patch
from studio import tts
from studio.paths import SKILL_DIR

class ReleaseTests(unittest.TestCase):
    def test_missing_lfm3_diagnostic_downloads_pinned_revision(self):
        with patch('importlib.util.find_spec',return_value=object()), patch.object(tts,'lfm3_model_path',return_value=None), patch.object(tts,'fish_model_path',return_value=None):
            status=tts.engine_status()['lfm3']
        self.assertIn(f'--revision {tts.LFM3_REVISION}',status)

    def test_scaffold_examples_quote_the_executable(self):
        text=(SKILL_DIR/'references/scaffold.md').read_text()
        self.assertIsNone(re.search(r'(?m)^\$STUDY\s',text))
        self.assertIn('STUDY="$SKILL/bin/study"',text)

if __name__=='__main__':unittest.main()
