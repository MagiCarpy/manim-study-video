"""studio.status must accept every checkpoint state other studio modules write."""
import tempfile
import unittest
from pathlib import Path

import yaml

from studio import status


def _section(base, state):
    root = Path(base) / 'sec'
    root.mkdir()
    (root / 'lesson.yaml').write_text(yaml.safe_dump({'title': 'T', 'scenes': []}))
    (root / 'checkpoint.yaml').write_text(yaml.safe_dump({'state': state, 'completed': []}))
    return root


class CheckpointStateTests(unittest.TestCase):
    def test_frozen_checkpoint_state_is_known(self):
        # `study checkpoint --freeze` writes state='frozen' and studio.workorders requires it.
        with tempfile.TemporaryDirectory() as d:
            result = status.section_status(_section(d, 'frozen'), 'sec', verify=False)
        self.assertFalse(any('unknown checkpoint state' in e for e in result['errors']), result['errors'])

    def test_bogus_checkpoint_state_still_reported(self):
        with tempfile.TemporaryDirectory() as d:
            result = status.section_status(_section(d, 'bogus'), 'sec', verify=False)
        self.assertTrue(any('unknown checkpoint state' in e for e in result['errors']))


if __name__ == '__main__':
    unittest.main()
