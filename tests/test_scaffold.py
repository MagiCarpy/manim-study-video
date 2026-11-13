"""Generated CLI briefs must work when checkout/workspace paths contain spaces."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from studio import scaffold

class BriefTests(unittest.TestCase):
    def test_generated_commands_quote_the_installed_executable(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root=Path(tmp);install=root/'skill checkout';wrapper=install/'bin/study'
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" >> "$RUN_LOG"\n')
            wrapper.chmod(0o755)
            lesson=root/'lesson folder';log=root/'argv.txt'
            with patch.object(scaffold,'SKILL_DIR',install):
                text=scaffold.brief('Example','Example',[('01-example',[1])],
                    {'engine':'lfm3','preset':'example'},1.0,root/'lock folder',lesson,False)
            commands=[line for line in text.splitlines() if line.startswith(('STUDY=','$STUDY ','"$STUDY" '))]
            result=subprocess.run(['bash','-e','-c','\n'.join(commands)],
                env=dict(os.environ,RUN_LOG=str(log)),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            args=log.read_text().splitlines()
            self.assertEqual(args.count(str(lesson)),3)
            self.assertEqual(args.count('narrate'),1)

if __name__=='__main__':unittest.main()
