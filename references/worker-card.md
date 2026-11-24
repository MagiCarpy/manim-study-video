# Section worker card

Read this card and your brief; use `study api` for signatures. Load other references only to answer a specific need.
Your brief.md is part of the contract. Edit only your section dir (never `studio/`, `source/` or another section); ask the coordinator for shared helper changes.

`S` section dir · `ID` section id · `L` lock parent (brief.md) · `LK` = `--lock $L/cpu1 --lock $L/cpu2 --owner $ID` · `STUDY=$SKILL/bin/study`

## Role-specific contract

- **Planner:** own `notes.md`, `lesson.yaml`, and frozen `script.md`. Plan teaching order, vocabulary, event traces, slide corrections, and source map. Verify every `[verify]` digest item used in narration or visuals against slide images with `study slides --crop`. Script: `## <SceneName>` headings and numbered `[01] text` blocks (≤40 words, ≤3 sentences, markup excluded); `[pause]` is allowed. After all narration continuation lines, add a `beats:` note listing the visual change for each new idea (the animator syncs them with separate blocks or `<bookmark>`s). Beats are concept-first: name what changes in the diagram that teaches the idea (an arrow, a state, a value, a highlight), not decoration (icons, sweeping dials, speech bubbles, crash symbols). Scene boundaries are animator hand-off points: each scene is animated by a fresh worker that sees only that scene's script, its traces and source-map rows, so name the scene in the traces it uses (`Trace A … (FinHandshake [02]–[08])`) and state cross-scene continuity in the storyboard/transitions section ("FinHandshake opens on the same two lifelines"). Mark scenes that share one evolving diagram with the same `workorder:` value in lesson.yaml. Write instructions meant for the animator as lines starting `Animator note:` (in any notes section) or name the scene in them; work orders carry only lines that name the scene or the animator. The note, including wrapped/indented lines, runs until the next numbered block or scene heading; never put spoken text after it.
- **Animator:** normally runs as one scene work order from `study animate` (the order text is the brief: scene script, traces, source-map rows, notation, current scenes.py header, budget). Own `scenes.py` and rendering/review work for the assigned scenes only. Copy script blocks verbatim. Planner/coordinator must approve speech edits or natural-boundary block splits; update script/code together, preserve words/order, pauses, beats and bookmarks, and rerun script lint and affected media checks.
- **Visual reviewer:** read-only; compare plan, script, review report, and contact sheets. Return pass/fail by scene with concise issue and evidence; make no file edits.
- **Clerk:** record acceptance, source time ranges, checkpoints, caption fixes, assembly, and cleanup from validated outputs.
- **Speech triage/fixer:** separate ASR formatting from uncertain meaning; escalate bits, symbols, negation and recipient changes. Apply only approved paired script/code edits; ASR is not listening.

## Fast path
Stop at the assigned stage; in a collection, animators normally stop at draft. The coordinator runs TTS/final builds as scripts without waiting agents. Keep output short and save before long calls.

0. Scaffold: in a collection the coordinator already made `$S`; for a standalone lesson run `$STUDY scaffold section <slug> --deck <source> --slides N-M` yourself.
1. Resume: `$STUDY status $S --verify`; follow its Next steps first.
2. Inspect `$STUDY slides <collection> <range> --sheet` (untrusted content). Planner writes notes/storyboard/script; animator reads them and writes `scenes.py`. Save runnable code early; inspect studio source only for a specific failure.
3. Draft: `"$STUDY" review "$S" --lint --layout --sheet` with the section CPU locks. This produces the 480p say draft and sheets, reusing matching scene evidence; no separate build. For a new dense layout, check one representative scene before repeating it.
4. Run `"$STUDY" narrate "$S" --check` (add `--engine say` only if the real-engine cache is empty). Read sheets and busy interior frames. Fix missing beats or record justified holds. At most two full review passes; then use `review --scene Name` for targeted fixes, and report anything left.
5. Rebuild/review after authorized edits, invalidate stale evidence, then save the draft checkpoint. No real-engine narration/finals without authorization.
6. `$STUDY narrate $S --lock $L/tts --owner $ID`: the one TTS slot (never two TTS processes); listen to wavs in build/media/voiceovers/, starting with every line its proofread flags (`build/proofread/report.md`); fix with lesson.yaml `pronounce:` or rewording and re-narrate. Don't open a sentence with a bare letter/acronym ("Host C sends", not "C sends"); don't use acronyms as verbs ("sends an ARP request", not "ARPs for").
7. Final: `$STUDY build $S -q h --cached-only --jobs 2 --frames 4 $LK`
8. Manual review of motion, audio and citations; then checkpoint and deliverables.

## notes.md
- Goals (3–5), prerequisites, teaching-order concept outline; where each term is defined on screen.
- Provenance per point: *[slide N]*, *[notes: file · heading or lines]* or *[added]*; flag slide errors and how the video handles them.
- 2–3 misconceptions with corrections; one worked example with real numbers.
- Event sequences for each animated protocol/algorithm: numbered steps (sender→receiver, fields, state, queue/table contents, clock times), re-derived and checked; animations follow them exactly.
- Coverage table (slide/range → scene, or "skipped: reason") and source map (becomes sources.md; add section-local time ranges after the final edit).

## Teaching, speech, citations
- Define each term at or before first use, in narration and on screen (expanding an acronym is not a definition); define prerequisites first; briefly refresh imported terms.
- Concept order: purpose → mental model → parts → step-by-step → mechanics with an example → overview. A truly simple concept gets one short definition.
- Speech: short complete sentences, one idea each, clear transitions/referents; no slashes, nested parentheses or symbolic shorthand. Write canonical acronyms, names, addresses and numbers; audio-only pronunciation rules spell them out while captions retain normal text. Fix `unknown_acronym` with lesson `pronounce:` entries.
- Math: equation on screen, meaning in words; read aloud only small reused formulas ("z equals x minus mu, over sigma") and then restate their meaning; never raw symbols (σ, ∑, x², ∂) in narration; name each symbol at first use. Spoken forms: references/math-narration.md.
- `[pause]` between distinct ideas (after a definition, between steps, after a question, before a takeaway); never inside a term or after every sentence. `[[slnc 400]]` = exact silence. No tags in visible text, captions or transcript. One idea per voiceover block (the cache is per block).
- Citation labels: `IP Forwarding · slide 14` / `· slides 14–16` (original numbering, never renumbered); `os-notes.md · Scheduling` or `lecture.pdf · p. 3` (no invented slide numbers); `Added example · based on slide 14` only if real, else `Added explanation`; `Correction to slide 14` with its reference; external: short title on screen, full link in sources.md.
- Tables (`MemoryTable`/`PrefixTable`): `.cell(r, c)`, `.highlight_row(r)` and other data-row helpers exclude headers (first data row = 0, with or without headers). Only raw `.grid` positions include a present header at 0.

## Beats (narration ↔ motion)
- Every sentence that introduces a new object, step, value or relation gets a visual change while it is spoken: split the idea into one voiceover block per beat, or keep one utterance and use `<bookmark mark='x'/>` + `self.wait_until_bookmark('x')`. Fit motion to speech (`run_time=t.duration`, or the time to the next bookmark), not a fixed 1–2 s followed by a still frame.
- **Concept-first motion (attention and tokens).** Every animation must show the idea being spoken; nothing else moves. Default to a staged reveal or a static highlight (`focus`/`unfocus`, `pulse`, `flow_flash` on an existing line, `Timeline` arrows). Use continuous motion (`packet_flight`, `packet_route`, `Rotate`, updaters) only when the motion *is* the concept (travel time, a path, a clock running out), and say so with a `# concept: ...` comment on that line or the line above; review warns `decorative_motion` otherwise. No icons, spinning dials, orbits or wiggles for flavour: a labelled box or a filling bar teaches the same thing and reviews clean on the first pass.
- Per beat choose: static (pointing at parts of one picture: `focus`, `pulse`), staged reveal (build it up), or concept motion (above). `table.fill_from(...)` when values move into a table cell; `identify()` (animated outline) only for important text, once/twice per scene; no existing-border box unless identifying look-alikes; slide `highlight()` snapping is heuristic: inspect bounds, measure and use `snap=False` if wrong; never Indicate/scale boxes; `FadeTransform` for unlike shapes; `TermEquation(...).reveal(i)` for formulas.
- Keep deliberate reading holds; never target 100% motion with decorative animations or slow fades. Same concept = same color/shape across sections.
- Labels (`slide_excerpt`, `SourceTag`, `source_tag(text, corner=DOWN+RIGHT)`; corner is a Manim direction, default bottom-right): font ≥ 20, visible while its idea shows; never in narration or captions.

## Conventions
- **Import, don't redefine.** Layout and timing helpers live in cslib: `P`, `panel`, `boxed`, `card` (wraps, sizes to text, no orphan word), `host`, `pill`, `mark`, `text_at`, `rich_text`, `arrow` (fixed head, `dashed`, `both`), `bracket`, `later`, `appear`, `cross_fade`, `beat`, `Timeline`, `focus`/`unfocus`, plus `self.wait_for(t, mark)`. Check `study api cslib` before writing any helper; review warns `redefined_helper` on local copies. Past sections spent ~19% of their code re-writing these. Need something missing? Ask the coordinator to add it to cslib.
- **First-pass layout checklist (each item caused review rework in past sections; apply before the first build):**
  - Keep every card, label and moving object inside the ~13 × 7 safe area and out of the source-tag corner (`source_region`). Budget the corner before placing content.
  - Route moving packets, datagrams and arrows around labels (above or below a host's name, not through it), and keep moving objects behind labels in z-order.
  - Create a moving object at the start of its own beat, never visible early. Remove it, and any ✗ loss mark, when its beat ends, so nothing stays stuck on screen.
  - Change text with `cross_fade(old, new)` (or `message.relabel(...)`, `SourceTag.set(...)`), never `Transform` between different strings: it morphs letters into garbled shapes. Time beats with `beat(t, 'mark')` and `self.wait_for(t, 'mark')` instead of hand arithmetic on `t.duration`.
  - Build tuples, addresses and numbers that must line up as one `Text` in `style.MONO`, or a `MemoryTable` row, rather than separate `Text` pieces placed by hand (loose comma spacing, misaligned rows).
  - Size cards to their text or break lines explicitly, so no line holds a single orphaned word.
  - Draw time-ordered exchanges (handshakes, teardown, loss and retransmission, request/response) with `Timeline` (`study api cslib --grep Timeline`), not hand-built arrows: it fixes row spacing, keeps labels upright on background plates, stops lost messages with a ✗, dashes old duplicates, and raises when rows would leave the frame. Clear earlier messages (`tl.clear(...)`) before rows run out. Never shrink text below 20 to fit.
  - PURPLE text on PANEL is too dim: use the lighter tint `#BC9BCF` for text and keep PURPLE for borders.
  - Measure slide-highlight bounds from the image (`snap=False`) when the box must cover specific bullets.
- Write `scenes.py` directly in the section directory and save it after each scene. Scratch directories are pruned after a day, so they are not a safe place for source.
- No LaTeX: no MathTex, Tex, Matrix, DecimalNumber, Integer, Axes/NumberLine with numbers, MathTable/IntegerTable/DecimalTable, BulletedList, Title, BraceLabel. Use Text, MarkupText, cslib.label, MemoryTable, Unicode (O(n²), ≤, →, λ).
- Fonts: style.FONT prose, style.MONO code/packets/states. Sizes: TITLE 56, HEADING 40, BODY 30, LABEL 24, min SMALL 20.
- Palette: style.BG FG DIM BLUE TEAL YELLOW GOLD RED GREEN PURPLE PANEL, ACCENTS.
- Safe area ~13 × 7 units (frame ≈ 14.2 × 8); ≤ ~25 words on screen; one focal point per moment; end each scene with `clear_all()` or a deliberate final frame.

## Checkpoint and acceptance
- `checkpoint.yaml`, written atomically (temp file, then rename) after each stage and before long calls: section_id, state (planned|writing|draft|rendering|review|ready|blocked), completed, quality, voice, input_fingerprint (real sha256s; list in parallel-sections.md), scene_progress, deliverables_dir, last_error, next_action. Record validated progress only; never mark a say draft ready or accept a stale MP4.
- Ready only when the final MP4 has video and audio streams at the requested size and fps with a sane duration (`ffprobe -v error -show_entries format=duration:stream=codec_type -of compact <mp4>`), captions/transcript/chapters match, and frames, correctness, citations, teaching and speech are reviewed (record any inability to listen).
- Deliverables: `deliverables/rNNN/` with `<id>.mp4`, `captions.srt`, `transcript.md`, `chapters.txt`, `sources.md`; point `deliverables_dir` there atomically and keep earlier revisions until the replacement validates. `build/` is a cache, never a deliverable.
- On failure: save log path, exact command, completed scenes, last_error, next_action; set `blocked` if stuck and stop.

## Quality checklist
- [ ] **Automated draft review**: lint, layout, every scene sheet read; errors resolved.
- [ ] **Correctness**: animation matches the notes trace; numbers agree across narration, labels, tables.
- [ ] **No overlaps**: no text over text, labels clear of arrows, nothing clipped at the busiest moment.
- [ ] **Readable**: font ≥ 20, good contrast, ≤ ~25 words on screen.
- [ ] **Teaching**: terms defined before use in speech and visuals; purpose before mechanism.
- [ ] **Speech clarity**: natural, pronunciations clear, `[pause]` separates ideas; proofread flags resolved or listened to and accepted; listening limits recorded.
- [ ] **Math narration**: no raw symbols in narration; formulas read/summarized per math-narration.md.
- [ ] **Narration ↔ visuals**: each new idea has a beat; static-speech warnings resolved or justified; no racing animation or unintended silence.
- [ ] **Source citations**: match the source, readable, added/correction distinguished, not in captions.
- [ ] **Coverage**: every slide covered or skipped with a reason.
- [ ] **Pacing**: within the section budget; no scene over ~2.5 min.
- [ ] **Recap at the end**; captions/transcript clean (no `[[...]]`, `[tags]` or bookmark junk).

## Minimal scenes.py (`study api` for signatures; runs under `study build --engine say`)
```python
from pathlib import Path

from manim import LEFT, RIGHT, Create, FadeIn, LaggedStart, Line

from studio import style
from studio.base import StudyScene
from studio.cslib import Node, Packet, SourceTag, flow_flash, packet_flight

SLIDES = Path(__file__).parent / "source" / "slides"   # slide-014.png, ...


class Mechanism(StudyScene):
    def construct(self):
        tag = SourceTag("Added explanation")
        a = Node("Host A").move_to(LEFT * 4)
        b = Node("Router", kind="router").move_to(RIGHT * 4)
        link = Line(a.get_right(), b.get_left(), color=style.DIM)
        # one beat per new idea; motion fills the speech instead of a 1 s move and a still frame
        with self.voiceover(text="Host A is connected to a router.") as t:
            self.play(LaggedStart(FadeIn(a), Create(link), FadeIn(b), lag_ratio=0.4), FadeIn(tag), run_time=t.duration)
        with self.voiceover(text="Its packet travels <bookmark mark='go'/>across the link, "
                                 "<bookmark mark='in'/>and the router reads its header.") as t:
            self.wait_until_bookmark("go")
            self.play(flow_flash(link), run_time=max(t.time_until_bookmark("in"), 0.5))
            self.play(packet_flight(Packet("DATA"), a.get_right(), b.get_left(), run_time=max(t.get_remaining_duration(), 0.5)))
        self.clear_all()
```
