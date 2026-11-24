"""Keep the copyable local-model setup tied to the runtime's pinned checkpoint."""
import ast
import re
import shlex
import subprocess
import unittest
from studio.paths import SKILL_DIR

class ReadmeSetupTests(unittest.TestCase):
    def test_first_run_targets_a_novice_with_a_local_agent(self):
        text=(SKILL_DIR/'README.md').read_text()
        self.assertIn('## Start here: ask your agent',text)
        self.assertLess(text.index('## Start here: ask your agent'),text.index('## Setup commands'))
        self.assertIn('PASTE_GITHUB_REPOSITORY_URL_HERE',text)
        for term in ('Claude','Antigravity','Codex','Hugging Face is','terminal','password','cached-only'):
            self.assertIn(term,text)
        skill=(SKILL_DIR/'SKILL.md').read_text()
        self.assertIn('## First-time setup',skill)
        self.assertIn('README.md#start-here-ask-your-agent',skill)

    def test_first_lfm3_recipe_creates_a_unique_project_and_strictly_checks_output(self):
        text=(SKILL_DIR/'references/voices.md').read_text()
        match=re.search(r'<!-- first-lfm3-bootstrap:start -->\s*```sh\n(.*?)\n```\s*<!-- first-lfm3-bootstrap:end -->',text,re.S)
        self.assertIsNotNone(match,'Missing executable first-run LFM3 recipe')
        assert match is not None
        script=match.group(1)
        result=subprocess.run(['bash','-n'],input=script,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        for term in ('set -eu','tempfile.mkdtemp','"engine": "lfm3"','--cached-only','--check','-xerror'):
            self.assertIn(term,script)
        self.assertIn('build/draft/${LESSON##*/}.mp4',script)
        python=re.search(r"<<'PY'\n(.*?)\nPY",script,re.S)
        self.assertIsNotNone(python)
        assert python is not None
        compile(python.group(1),'first-lfm3-bootstrap','exec')

    def test_onboarding_readme_anchors_exist(self):
        readme=(SKILL_DIR/'README.md').resolve()
        headings=re.findall(r'^#{1,6}\s+(.+)$',readme.read_text(),re.M)
        anchors={re.sub(r'[^\w -]','',heading.lower()).replace(' ','-') for heading in headings}
        for name in ('README.md','SKILL.md','references/voices.md'):
            source=SKILL_DIR/name
            for destination in re.findall(r'\]\(([^)\s]+)\)',source.read_text()):
                if destination.startswith(('https:','http:')) or '#' not in destination:continue
                path,anchor=destination.split('#',1)
                if (source.parent/path).resolve()==readme:
                    self.assertIn(anchor,anchors,f'{name}: {destination}')

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
        self.assertIn('token',kwargs,'First-time download must not require or implicitly send credentials')
        self.assertEqual(ast.unparse(kwargs['token']),'False')

if __name__=='__main__':unittest.main()
