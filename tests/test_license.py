"""The explicitly selected project license must be distributed with the source."""
import tomllib
import unittest
from studio.paths import SKILL_DIR

class LicenseTests(unittest.TestCase):
    def test_mit_notice_matches_package_metadata(self):
        path=SKILL_DIR/'LICENSE'
        self.assertTrue(path.is_file(),'Missing selected MIT license')
        text=path.read_text()
        self.assertIn('MIT License',text)
        self.assertIn('make-study-video contributors',text)
        self.assertIn('Permission is hereby granted',text)
        metadata=tomllib.loads((SKILL_DIR/'pyproject.toml').read_text())
        self.assertEqual(metadata['project']['license'],'MIT')
        self.assertIn('LICENSE',metadata['project']['license-files'])
        self.assertNotIn('not yet been selected',(SKILL_DIR/'README.md').read_text())

if __name__=='__main__':unittest.main()
