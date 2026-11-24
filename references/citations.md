# Source citations in the video

Show a small source label while the relevant idea or animation is visible, including custom
animations based on the input, not only slide excerpts. Use a consistent quiet corner inside
the safe area, good contrast, and font size ≥ 20; reserve space clear of diagrams and captions.
Use existing `Text`/`cslib.label`, without LaTeX. Keep the label visible long enough to read;
update it when the source changes within a scene and restore it after clearing the scene.

- Slides: `IP Forwarding · slide 14` or `IP Forwarding · slides 14–16`. Keep original deck
  numbering across sections; distinguish decks with short titles. If printed slide numbers
  differ from PDF pages, record that relationship and use an unambiguous locator.
- Notes: `os-notes.md · Scheduling` or `lecture.pdf · p. 3`; use heading, page, or stable
  line ranges that exist in the original input. Do not invent slide numbers for notes.
- Added examples: `Added example · based on slide 14` only when that connection is real;
  otherwise `Added explanation`. For corrections, use `Correction to slide 14` and record
  the supporting reference separately. Never attribute new numbers or corrected claims to
  the original as though they appeared there. Cite external claims by short source title
  on screen, with the full reference/link in the source map.

Extend the existing `notes.md` coverage table into a source map: scene/visual beat → original
file and exact locator → displayed label → provenance (source, added, or correction).
Keep the scaffolded columns (`Slide | Scene [blocks] | Locator | Displayed label | Provenance |
Actual times`); name blocks as `Ports [01]–[03], [05]` or `Ports (all)`. Put the input file,
author/course credit and numbering in `credits:` (collection.yaml, or lesson.yaml for a single
lesson); the scaffold leaves a TODO there on purpose. After the final build, run
`$STUDY sources <section>` (or `<collection>` for every section): it aligns script blocks to the
final captions, writes `build/sources.md` and `build/sources.json` with measured section-local
times, and appends the notes' reference/correction sections and `External:` lines. It fails,
writing nothing, if any row names a block that is not in the script or if `credits:` has TODO.
After assembly, `$STUDY sources <collection> --combined` shifts every row by the combined video's
measured chapter starts. Copy `sources.md` beside the delivered MP4. Keep citations visual; do not make narration read them
or insert them into speech captions. A bare-topic lesson can use `Added explanation` and
cite any references actually consulted; never fabricate input citations.
