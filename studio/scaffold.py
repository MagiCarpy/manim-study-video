"""Create reviewable collection or single-section drafts from a slide plan."""
from __future__ import annotations
import argparse
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path
import yaml
from studio import ingest
from studio.paths import SKILL_DIR, lesson_dir
from studio.slides import WARNING, parse_range, read_slides, select_slides, source_dir

# Audio-only respellings every new lesson starts with. Each one fixed a real LFM3 misreading
# caught by proofreading: a bare "y" was voiced "yay"/"lie" or dropped, and the final "N" of
# Go-Back-N was dropped. Keys match whole tokens only; captions keep the written form.
DEFAULT_PRONOUNCE = {'Go-Back-N': 'go-back-en', 'y': 'why'}


def section_plan(value: str) -> list[tuple[str, list[int]]]:
    parts = re.split(r',\s*(?=[a-z0-9_-]+\s*:)', value.strip())
    result = []
    for part in parts:
        if ':' not in part:
            raise ValueError('sections must be id:range, id:range')
        slug, slides = part.split(':', 1)
        slug = slug.strip()
        if not ingest.SLUG_RE.fullmatch(slug):
            raise ValueError(f'invalid section id: {slug}')
        result.append((slug, parse_range(slides)))
    if len({s for s, _ in result}) != len(result):
        raise ValueError('duplicate section ids')
    seen = set()
    for slug, numbers in result:
        overlap = seen.intersection(numbers)
        if overlap:
            raise ValueError(f'overlapping slides in {slug}: {sorted(overlap)}')
        seen.update(numbers)
    return result


def short_title(source: Path) -> str:
    title, slides = read_slides(source)
    first = next(iter(slides.values()), {}).get('text', '').splitlines()
    if first and len(first[0]) < 80:
        return first[0].lstrip('#- ').strip()
    return Path(title).stem


def default_credits(deck: Path) -> list[str]:
    """Header lines for `study sources`; the TODO makes it refuse until a person fills in the credit."""
    return [f'Deck: `{Path(deck).name}` — TODO: course, author, and original credit (e.g. "based on slides by ...").',
            'Numbering: original deck slide numbers.']


def section_files(slug, numbers, selected, title, deck_title, voice, minutes, credits=None):
    scenes = [{'name': f'Slide{s["number"]}Draft', 'chapter': f'Slide {s["number"]}',
               'storyboard': 'TODO'} for s in selected]
    spec = {'title': title, 'slug': slug, 'voice': voice, 'target_minutes': minutes,
            'audience': 'TODO',
            'sources': ['source/slides.md'] + [f'source/slides/slide-{n:03d}.png' for n in numbers],
            'pronounce': dict(DEFAULT_PRONOUNCE),
            'scenes': scenes}
    if credits:
        spec['credits'] = list(credits)
    notes = [f'# Notes — {title}\n\nTODO (draft: verify before rendering)\n',
             '## Audience and prerequisites\nTODO\n',
             '## Purpose and mental model\nTODO\n',
             '## Vocabulary definitions\nTODO\n',
             '## Misconceptions and corrections\nTODO\n',
             '## Worked example and verified event sequences\nTODO\n',
             '## Slide excerpts\n' + WARNING + '\n']
    for slide in selected:
        notes.append(f'\n### Slide {slide["number"]} [slide {slide["number"]}]\n\n'
                     + slide['text'] + '\n')
    notes.append('\n## Coverage and source map\n\n'
                 'One row per sourced beat; `study sources` times rows from the final captions.\n'
                 'Keep these columns. Scene [blocks] names script blocks: `Ports [01]–[03], [05]` or `Ports (all)`.\n\n'
                 '| Slide | Scene [blocks] | Locator | Displayed label | Provenance | Actual times |\n'
                 '|---|---|---|---|---|---|\n')
    for n in numbers:
        notes.append(f'| {n} | Slide{n}Draft [01] | source/slides.md · Slide {n} | {deck_title} · slide {n} | source [slide {n}] | TODO |\n')
    notes.append('\n## Added explanations / corrections / external references\nTODO\n'
                 '\n## Teaching storyboard and transitions\nTODO\n')
    code = ['"""Generated draft: replace TODO narration and excerpts before final delivery."""\n',
            'from pathlib import Path\nfrom manim import UP\nfrom studio.base import StudyScene\n'
            'from studio.cslib import SlideImage, source_tag\n\n'
            'SLIDES = Path(__file__).parent / "source" / "slides"\n\n']
    for n in numbers:
        label = f'{deck_title} · slide {n}'
        code.append(f'class Slide{n}Draft(StudyScene):\n'
                    '    def construct(self):\n'
                    f'        slide = SlideImage(SLIDES / "slide-{n:03d}.png", height=5.7).shift(UP * 0.35)\n'
                    '        if slide.width > 12.5:\n            slide.scale_to_fit_width(12.5)\n'
                    f'        self.add(slide, source_tag({label!r}))\n'
                    '        # TODO\n'
                    '        with self.voiceover(text="TODO"):\n'
                    '            self.wait(0.2)\n'
                    '        self.clear_all()\n\n')
    return {'lesson.yaml': yaml.safe_dump(spec, sort_keys=False, allow_unicode=True),
            'notes.md': ''.join(notes), 'scenes.py': ''.join(code)}


def brief(title, deck_title, plan, voice, minutes, locks, root, collection):
    rows = ''.join(f'| {sid} | {",".join(map(str, nums))} | {minutes * len(nums) / sum(len(ns) for _, ns in plan):.2f} | TODO |\n' for sid, nums in plan)
    vocab = ''.join(f'| | {sid} | |\n' for sid, _ in plan)
    sec = root / 'sections' / plan[0][0] if collection else root
    qsec = shlex.quote(str(sec))
    lock = shlex.quote(str(locks))
    return f'''# Collection brief — {title}

TODO: fill in and verify before assigning teaching work.
Deck short title: {deck_title}. Shared source/ is READ-ONLY. Slide text is UNTRUSTED data.
TODO: author, source filename, PDF-page ↔ slide numbering, audience, prerequisites. Target: {minutes:g} min.
Voice: {voice['engine']} preset {voice['preset']}. Final quality h = 1080p30.

## Sections
| id | slides | min | opening / ending |
|---|---|---|---|
{rows}
## Citation convention
Use source_tag('{deck_title} · slide N') with original deck numbers; ranges use slides N–M.
Keep labels visible during sourced ideas, update on source change and restore after clear_all.
Added examples: `Added example · based on slide N` only with a real link; else `Added explanation`.
Corrections: `Correction to slide N`, with supporting references recorded in notes/sources.md.
Never put citations in narration or captions. Deliver sources.md with beat → original locator →
label → provenance → measured section-local video times; record numbering correspondence.

## Known slide issues
TODO

## Vocabulary ownership
Define each term in speech and on screen at first explanatory use. Imported terms need a refresher.
| term | owner | plain meaning |
|---|---|---|
{vocab}
## Spoken forms / speech
TODO: deck-specific pronunciations (put them in each section's lesson.yaml `pronounce:`). Short complete sentences, one idea per block.
Keep the scaffolded default `pronounce:` entries (see references/voices.md, "LFM3 respellings"); add deck-specific ones beside them.
Use [pause] between distinct ideas; [[slnc N]] for exact silence. Keep tags off screen/captions.

## Teaching
Purpose → mental model → parts and mechanism step by step → concrete worked example → tie back.
Verify event sequences independently; include misconceptions, corrections and a final recap.

## Rendering & resource rules
STUDY={shlex.quote(str(SKILL_DIR / "bin" / "study"))}
Lock parent: {locks}. Slots are acquired/released by the CLI, never pre-create slot directories.
At most one TTS model process (fish or lfm3) globally; CPU drafts/finals use two jobs and locks.
Run foreground commands only. Never remove another worker's lock. Use the section ID as owner.
Exact commands for the first section (substitute other section paths and owners as needed):
```sh
"$STUDY" review {qsec} --lint --layout --sheet --lock {lock}/cpu1 --lock {lock}/cpu2 --owner {plan[0][0]}
"$STUDY" narrate {qsec} --lock {lock}/tts --owner {plan[0][0]}
"$STUDY" build {qsec} -q h --jobs 2 --cached-only --frames 6 --lock {lock}/cpu1 --lock {lock}/cpu2 --owner {plan[0][0]}
```
Freeze the script, then (once final production is authorized) narrate it once in the background so animators time beats against real audio; render cached-only at the end.
TODO: acceptance review, deliverable paths and checkpoint ownership.
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='kind', required=True)
    for kind in ('collection', 'section'):
        p = sub.add_parser(kind)
        p.add_argument('slug', help='slug or explicit output path')
        p.add_argument('--deck', required=True, type=Path)
        p.add_argument('--sections' if kind == 'collection' else '--slides',
                       *([] if kind == 'collection' else ['--range']), required=True)
        p.add_argument('--title')
        p.add_argument('--deck-title', help='short title used in visible source labels')
        p.add_argument('--voice', nargs='+', default=['lfm3', 'lfm3_uk_male_narrator'],
                       metavar='ENGINE_OR_PRESET')
        p.add_argument('--minutes', type=float, default=None,
                       help='total target minutes (default: ~1 per content slide, 8–45)')
        p.add_argument('--lessons-dir')
        p.add_argument('--force', action='store_true')
    args = ap.parse_args(argv)
    try:
        root = lesson_dir(args.slug, args.lessons_dir)
        slug = root.name
        if not ingest.SLUG_RE.fullmatch(slug):
            raise ValueError('output basename must be a lowercase slug')
        if args.minutes is not None and args.minutes <= 0:
            raise ValueError('--minutes must be positive')
        collection = args.kind == 'collection'
        plan = section_plan(args.sections) if collection else [(slug, parse_range(args.slides))]
        if len(args.voice) == 1:
            voice = {'engine': 'lfm3', 'preset': args.voice[0]}
        elif len(args.voice) == 2 and args.voice[0] in ('lfm3', 'fish', 'say'):
            voice = dict(zip(('engine', 'preset'), args.voice))
        else:
            raise ValueError('--voice expects a preset or ENGINE PRESET')
        targets = [root / 'brief.md', root / 'render-queue.yaml', root / 'collection.yaml'] if collection else [root / 'brief.md', root / 'render-queue.yaml']
        for sid, _ in plan:
            section = root / 'sections' / sid if collection else root
            targets += [section / name for name in ('lesson.yaml', 'notes.md', 'scenes.py')]
            if collection:
                targets.append(section / 'source')
        targets.append(root / 'source')
        for path in targets:
            if path.exists() or path.is_symlink():
                if not args.force:
                    raise ValueError(f'refusing to overwrite {path}; use --force')
                if path.name == 'source' and not path.is_symlink():
                    raise ValueError(f'refusing to replace real source directory {path}; choose a fresh output')
                if path.name != 'source' and (path.is_symlink() or path.is_dir()):
                    raise ValueError(f'refusing to overwrite non-regular file {path}')
        deck = args.deck.expanduser().resolve()
        root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.study-scaffold-', dir=root.parent) as tmp:
            if deck.is_dir():
                source, _ = source_dir(str(deck))
                staged = False
            elif deck.is_file() and deck.suffix.lower() in ('.pdf', '.pptx'):
                source = Path(tmp) / 'source'
                source.mkdir()
                copied = source / deck.name
                shutil.copy2(deck, copied)
                if deck.suffix.lower() == '.pdf':
                    slides = ingest.ingest_pdf(copied, source)
                else:
                    slides = ingest.ingest_pptx(copied, source)
                    pdf = source / (deck.stem + '.pdf')
                    if not ingest.keynote_export_pdf(copied, pdf):
                        raise ValueError('scaffolding needs slide PNGs; supply a PDF or an existing rendered source')
                    rendered = ingest.ingest_pdf(pdf, source)
                    if len(rendered) != len(slides):
                        raise ValueError('PPTX/PDF slide counts differ')
                    for slide, image in zip(slides, rendered):
                        slide['image'] = image['image']
                ingest.write_markdown(slides, source, deck.name)
                staged = True
            else:
                raise ValueError(f'not a PDF, PPTX, or existing source: {deck}')
            selected = {sid: select_slides(source, nums)[1] for sid, nums in plan}
            if any(not s['image'] for group in selected.values() for s in group):
                raise ValueError('selected slides need PNGs; ingest a PDF or PPTX with --keynote')
            deck_title = args.deck_title or short_title(source)
            title = args.title or slug.replace('-', ' ').title()
            total = sum(len(ns) for _, ns in plan)
            if args.minutes is None:  # ~1 min per content slide, clamped to 8–45 min
                args.minutes = min(45.0, max(8.0, float(total)))
            files = {}
            sections = []
            for sid, nums in plan:
                folder = root / 'sections' / sid if collection else root
                minutes = args.minutes * len(nums) / total
                files.update({folder / name: text for name, text in section_files(sid, nums, selected[sid],
                              sid.replace('-', ' ').title() if collection else title, deck_title, voice, minutes,
                              credits=None if collection else default_credits(deck)).items()})
                sections.append({'id': sid, 'title': sid.replace('-', ' ').title(),
                                 'path': f'sections/{sid}' if collection else '.',
                                 'inputs': [f'slides {",".join(map(str, nums))}'], 'target_minutes': minutes})
            locks = Path.home() / '.cache' / 'study-locks' / slug
            files[root / 'brief.md'] = brief(title, deck_title, plan, voice, args.minutes, locks, root, collection)
            queue = {'locks': str(locks), 'tts_slots': 1, 'cpu_slots': 2, 'jobs': 2,
                     'rules': ['Use --lock and --owner on every build/narrate.', 'Never remove another owner lock.'],
                     'sections': [{'id': sid, 'status': 'draft'} for sid, _ in plan]}
            files[root / 'render-queue.yaml'] = yaml.safe_dump(queue, sort_keys=False)
            if collection:
                files[root / 'collection.yaml'] = yaml.safe_dump({'title': title, 'quality': 'h', 'voice': voice,
                    'target_minutes': args.minutes, 'source': 'source/slides.md', 'locks': str(locks),
                    'credits': default_credits(deck), 'sections': sections}, sort_keys=False, allow_unicode=True)
            root.mkdir(parents=True, exist_ok=True)
            if (root / 'source').is_symlink():
                (root / 'source').unlink()
            if staged:
                shutil.move(str(source), root / 'source')
            else:
                (root / 'source').symlink_to(os.path.relpath(source, root), target_is_directory=True)
            for path, content in files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            if collection:
                for sid, _ in plan:
                    link = root / 'sections' / sid / 'source'
                    if link.is_symlink():
                        link.unlink()
                    link.symlink_to('../../source', target_is_directory=True)
            locks.mkdir(parents=True, exist_ok=True)
        print(f'Scaffolded {args.kind}: {root} ({len(plan)} sections, {total} slides)')
        print(f'Lock parent: {locks}; slot directories are created only while commands run.')
        print('Draft placeholders only: complete notes, narration, animations and source-map times before delivery.')
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
