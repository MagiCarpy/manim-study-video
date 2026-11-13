# Slide packs and project scaffolds

Run from the project root using `STUDY=$SKILL/bin/study`.

```sh
$STUDY slides lessons/ip-forwarding-s16-31 16-17 --sheet
$STUDY slides lessons/ip-forwarding-s16-31/source 26-30 --sheet ./lookup.png --cols 2 --json
$STUDY scaffold collection forwarding-part2 --deck lessons/ip-forwarding-s16-31/source --sections '05-longest-prefix:16-17, 06-routing:18-19' --title 'IP Forwarding, Part 2' --deck-title 'IP Forwarding' --voice lfm3 lfm3_uk_male_narrator --minutes 15
$STUDY scaffold section forwarding-prefix --deck lessons/ip-forwarding-s16-31/source --slides 16-17 --minutes 3
```

`slides` accepts a lesson, collection, source directory or lesson slug, and comma-separated
slide numbers/ranges. It prints exactly the selected text marked UNTRUSTED, plus PNG paths.
`--json` emits the warning, deck title, source, slide records and sheet paths in one object.
`--sheet [OUT.png]` writes labeled PNG contact sheets: at most four slides per sheet, 1280px
per column, two columns by default (`--cols 1..4`). Additional sheets use `-02`, `-03`, etc.
Without OUT, sheets are cached under the lesson/collection `build/slides/`. For a source directory,
this is the source's parent. Missing requested slides or missing sheet images fail clearly.

Scaffolds reuse existing sources through symlinks, or ingest a PDF/PPTX once into the collection's
source. PPTX rendering tries Keynote by bundle ID, then headless LibreOffice; if neither works,
export a PDF manually. The original PPTX is kept. Existing sources are never modified.

Collection outputs: `collection.yaml`, `render-queue.yaml`, a template `brief.md`, and
`sections/<id>/{source,lesson.yaml,notes.md,scenes.py}`. Single sections put those lesson files
at the output root and accept `--slides` (alias `--range`). Bare output slugs use `~/study-videos/lessons/`,
`$STUDY_LESSONS_DIR`, or `--lessons-dir`; explicit output paths are supported. IDs must be lowercase
slugs; duplicate IDs and overlapping collection ranges are rejected. Target minutes are split
in proportion to assigned slide counts. `--voice PRESET` uses lfm3; `--voice ENGINE PRESET` is explicit.

Notes contain the original excerpts, provenance tags and one coverage/source-map row per slide.
Each generated scene displays a slide with a source tag and short TODO narration. These are
buildable drafts, not finished teaching videos. Fill in vocabulary definitions, independent
traces, examples, corrections, substantive animations, narration and measured citation times.
Use `--deck-title` to override the automatically inferred first-slide title for citation labels.
The brief includes citation/speech/teaching policy and exact draft/narrate/final lock commands.
The scaffold creates `~/.cache/study-locks/<slug>/` only; the CLI manages `tts`, `cpu1`, `cpu2`
slot directories while commands run. Never pre-create occupied slot directories.

Files are refused before writing if any generated target exists, unless `--force` is passed.
Force replaces only generated files/symlinks; it refuses real existing source directories and
symlinked output files. Use a fresh output path when re-ingesting a source deck.

```sh
$STUDY build lessons/forwarding-part2/sections/05-longest-prefix --engine say --jobs 2 --lock ~/.cache/study-locks/forwarding-part2/cpu1 --lock ~/.cache/study-locks/forwarding-part2/cpu2 --owner 05-longest-prefix
```
