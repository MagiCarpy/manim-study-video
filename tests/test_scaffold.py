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


class SourcesScaffoldTests(unittest.TestCase):
    """Scaffolded files feed `study sources` directly."""

    def files(self, **kw):
        return scaffold.section_files('s', [3], [{'number': 3, 'text': 'x'}], 'T', 'Deck',
                                      {'engine': 'say'}, 2.0, **kw)

    def test_notes_source_map_parses_and_names_blocks(self):
        from studio import sources
        notes = self.files()['notes.md']
        idx, rows = sources._table(notes)
        table = [l for l in notes.split('source map')[1].splitlines() if l.startswith('|')]
        header = [h.strip().lower() for h in table[0].strip('|').split('|')]
        self.assertIn('scene [blocks]', header)
        self.assertEqual(rows[0][idx['slide']], '3')
        self.assertIn('[01]', rows[0][idx['beat']])

    def test_credit_placeholder_is_explicit_todo_naming_the_deck(self):
        lines = scaffold.default_credits(Path('/x/transportprotocols2026.pptx'))
        self.assertTrue(any('`transportprotocols2026.pptx`' in l for l in lines))
        self.assertTrue(any('TODO' in l for l in lines))  # `study sources` refuses until filled

    def test_single_lesson_carries_credits_in_lesson_yaml(self):
        import yaml
        spec = yaml.safe_load(self.files(credits=['Deck: a'])['lesson.yaml'])
        self.assertEqual(spec['credits'], ['Deck: a'])
        self.assertNotIn('credits', yaml.safe_load(self.files()['lesson.yaml']))


class DefaultPronounceTests(unittest.TestCase):
    """New lessons start with respellings that fixed real LFM3 misreadings."""

    def lesson(self, engine='lfm3'):
        import yaml
        files = scaffold.section_files('s', [1], [{'number': 1, 'text': 'x'}], 'T', 'Deck',
                                       {'engine': engine, 'preset': 'p'}, 2.0)
        return yaml.safe_load(files['lesson.yaml'])

    def test_scaffolded_lesson_carries_default_respellings(self):
        spec = self.lesson()
        self.assertEqual(spec['pronounce'], scaffold.DEFAULT_PRONOUNCE)
        self.assertEqual(spec['pronounce']['Go-Back-N'], 'go-back-en')
        self.assertEqual(spec['pronounce']['y'], 'why')

    def test_defaults_respell_only_whole_tokens(self):
        from studio import tts
        saved = dict(tts.LESSON_PRONOUNCE)
        try:
            tts.LESSON_PRONOUNCE.clear(); tts.LESSON_PRONOUNCE.update(scaffold.DEFAULT_PRONOUNCE)
            self.assertEqual(tts.spoken_text('The server picks y, then Go-Back-N resends.'),
                             'The server picks why, then go-back-en resends.')
            for kept in ('yes', 'y-axis', 'Y', 'mystery', 'Go-Back-Nine'):
                self.assertNotIn('why', tts.spoken_text(kept))
        finally:
            tts.LESSON_PRONOUNCE.clear(); tts.LESSON_PRONOUNCE.update(saved)

    def test_brief_tells_planners_to_keep_defaults(self):
        text = scaffold.brief('Example', 'Example', [('01-example', [1])],
                              {'engine': 'lfm3', 'preset': 'p'}, 1.0, Path('/tmp/l'), Path('/tmp/x'), False)
        self.assertIn('Keep the scaffolded default `pronounce:` entries', text)

if __name__=='__main__':unittest.main()
