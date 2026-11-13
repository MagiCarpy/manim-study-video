"""Keep the copyable local-model setup tied to the runtime's pinned checkpoint."""
import ast
import re
import shlex
import subprocess
import unittest
from studio.paths import SKILL_DIR

class ReadmeSetupTests(unittest.TestCase):
    def test_pinned_download_command_is_copyable_and_matches_runtime(self):
        text=(SKILL_DIR/'README.md').read_text()
        match=re.search(r'### Download the pinned checkpoint.*?```sh\n(.*?)\n```',text,re.S)
        self.assertIsNotNone(match,'README needs an explicit pinned-model download command')
        assert match is not None
        script=match.group(1)
        result=subprocess.run(['bash','-n'],input=script,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        argv=shlex.split(script.replace('\\\n',' '))
        self.assertIn('HF_HUB_OFFLINE=0',argv)
        code=ast.parse(argv[argv.index('-c')+1])
        imports={alias.name for node in ast.walk(code) if isinstance(node,ast.ImportFrom) and node.module=='studio.tts' for alias in node.names}
        self.assertTrue({'LFM3_MODEL','LFM3_REVISION'}<=imports)
        calls=[node for node in ast.walk(code) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='snapshot_download']
        self.assertEqual(len(calls),1)
        kwargs={item.arg:item.value for item in calls[0].keywords}
        self.assertEqual(ast.unparse(kwargs['repo_id']),'LFM3_MODEL')
        self.assertEqual(ast.unparse(kwargs['revision']),'LFM3_REVISION')

if __name__=='__main__':unittest.main()
