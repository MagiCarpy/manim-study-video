"""Public CI must check generation without private datasets or model downloads."""
import ast
import unittest
import yaml
from studio.paths import SKILL_DIR

class CITests(unittest.TestCase):
    def test_smoke_full_decode_ffmpeg_exits_on_errors(self):
        tree=ast.parse((SKILL_DIR/'tests/smoke.py').read_text())
        decode_calls=[node for node in ast.walk(tree)
                      if isinstance(node,ast.Call)
                      and isinstance(node.func,ast.Attribute)
                      and isinstance(node.func.value,ast.Name)
                      and node.func.value.id=='subprocess'
                      and node.func.attr=='run'
                      and node.args and isinstance(node.args[0],ast.List)
                      and isinstance(node.args[0].elts[0],ast.Constant)
                      and node.args[0].elts[0].value=='ffmpeg']
        self.assertEqual(len(decode_calls),1,'Expected one smoke full-decode command')
        command_node=decode_calls[0].args[0]
        assert isinstance(command_node,ast.List)
        command=[arg.value if isinstance(arg,ast.Constant) else None
                 for arg in command_node.elts]
        self.assertEqual(command[-3:],['-f','null','-'])
        self.assertIn('-xerror',command,'Smoke full decoding must fail on decode errors')
        self.assertLess(command.index('-xerror'),command.index('-i'))

    def test_workflow_runs_public_tests_and_model_free_smoke(self):
        path=SKILL_DIR/'.github/workflows/checks.yml'
        self.assertTrue(path.is_file(),'Missing public generation CI')
        workflow=yaml.safe_load(path.read_text())
        self.assertEqual(workflow['permissions'],{'contents':'read'})
        commands='\n'.join(step.get('run','') for step in workflow['jobs']['macos']['steps'])
        self.assertIn('unittest discover',commands)
        self.assertIn('tests/smoke.py',commands)
        self.assertNotIn('setup --lfm3',commands)
        self.assertNotIn('snapshot_download',commands)
        self.assertTrue((SKILL_DIR/'tests/smoke.py').is_file())

if __name__=='__main__':unittest.main()
