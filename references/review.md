# Automated draft review

Run the draft loop from the project containing `lessons/` (or pass a lesson path):

```sh
STUDY="$SKILL/bin/study"
"$STUDY" review <lesson> --lint --layout --sheet \
  --lock ~/.cache/study-locks/skill-dev/cpu1 \
  --lock ~/.cache/study-locks/skill-dev/cpu2 --owner review
# Repeat --scene Name for targeted changes. Do not pre-build the draft.
# Read build/review/report.md and one contact sheet per scene; fix and repeat.
```

`review` writes `build/review/report.md` and `report.json`, with PASS/FAIL at the top,
selected checks, issues with source lines or scene times/narration, and timing data.
Errors give exit code 1; warnings alone give 0. A PASS covers only selected checks.
No flags defaults to `--lint --sheet`. `--lessons-dir` follows other study commands.

- `--lint` parses `scenes.py` without executing it. Checks known LaTeX constructors
  (including import aliases), literal font sizes below 20, narration over 40 words
  or three sentences, spelled `I P`, direct `source_tag` usage in every configured
  scene, configured class names, and tags/bookmarks in generated captions/transcript.
  Missing sidecars and dynamic narration are warnings: build or inspect manually.
- `--layout` always uses 480p15, `say`, two jobs, owner `review`, and the two CPU
  slot locks above (override with repeatable `--lock` and `--owner`). It never loads
  a speech model. A scene's layout is reused only while its artifact stamps and
  input fingerprint match. Inputs include `lesson.yaml`, top-level lesson Python,
  `source/`, `assets/` and studio Python. Keep render dependencies in those paths.
  Targeted lint excludes other configured scenes and generated section sidecars;
  run full lint before acceptance. Layout stays a draft check even with `-q h`.
- `--sheet` reads existing renders and writes `<Scene>.png`: eight evenly spaced
  frames plus frames 0.1 seconds after known source-change endpoints from matching draft layout recordings.
  `-q l` (default) uses 480p15; `-q h` uses 1080p30. High-quality sheets use eight
  frames only, because another voice/quality render may have different timing.
  Missing or unreadable renders are errors. Images are labeled with scene/time.

For an explicit draft build when you also need layout evidence, keep recording enabled so a subsequent review can reuse it:

```sh
"$STUDY" build <lesson> --engine say --review --jobs 2 \
  --lock ~/.cache/study-locks/skill-dev/cpu1 \
  --lock ~/.cache/study-locks/skill-dev/cpu2 --owner review
```

`StudyScene` samples after each `play()` / `wait()`, recording visible `Text` and
`MarkupText` (including cslib labels), glyph bounds, effective font size, renderer
clock and active narration. It reports parts outside the centered 13 × 7 safe area
(with 0.02-unit numerical tolerance), text overlaps greater than 0.02 square units
and 12% of the smaller box, and non-source text in the reserved bottom-right region
(x=0…7.12, y=−4…−3). Geometry stays unchanged. Per-scene recorder time excludes JSON
serialization/I/O; avoid redundant samples while retaining useful review coverage.

## Stream acceptance and smoke checks

Probe metadata, then decode the entire output; metadata alone does not establish stream integrity:

```sh
ffprobe -v error -show_streams -show_format -of json "$VIDEO"
ffmpeg -v error -xerror -i "$VIDEO" -f null -
```

Require both commands to exit successfully before reporting acceptance. Keep `-xerror` before `-i`: logging at error level does not make every decode error fatal. Preserve a regression test for this command policy so later simplification cannot silently weaken CI. Require expected audio/video streams, positive duration within the fixture budget and the requested dimensions; successful decoding does not prove narration or visual quality.

Run deterministic smoke checks from a fresh locked environment using a new source-only fixture directory. Refuse existing output paths and retain failure logs; never use an accepted lecture as a test target. Test base-only installation separately from optional-engine installation, because installed extras can hide undeclared dependencies. Report public and private test counts separately. A local equivalent is not a hosted CI run.

For source-only example lint, distinguish expected missing generated sidecars from source/script errors. Scope any exception to that fixture and warning; never weaken production lint or omit final rendered-sidecar checks.

## Limits and manual review

Snapshots miss transient mid-animation collisions, direct add/remove changes until
the next play/wait, glyphs converted to other object types, text inside slide images,
and obscured objects still present behind opaque panels. Bounds are axis aligned:
rotated text, multiline whitespace, deliberate text-on-text, and safe-area violations
in existing corner source tags may need human judgment. Shapes, arrows, panel
containment, contrast, text semantics and correctness are not assessed. Separate
text objects are checked even if one contains the other. Source tags use optional
`_studio_source_tag` metadata or lower-corner citation wording; custom sources may
need the metadata. Transform text is tracked for explicit Transform targets;
complex custom transforms may retain stale strings while geometry remains current.

Static checks cannot resolve arbitrary helpers, inherited source tags, dynamic
strings, sizes computed from expressions or nested Axes configuration. Sentence
counts are approximate. A source_tag call does not prove citation visibility or
accuracy. Source-change frames follow recorded endpoints by 0.1 seconds to avoid decoding
the last transition frame; they are not exact transition start times.
No check verifies subject matter, source coverage, narration pronunciation/pacing,
Fish pauses, audio quality, captions' meaning, or teaching quality. Inspect the
report and sheets, then manually review representative motion and audio before a
final render. Automated findings are candidates for fixing, not automatic edits.
