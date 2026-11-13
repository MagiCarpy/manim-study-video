# Parallel sections, checkpoints, and assembly

Use independent sections for multi-topic input; retain standalone videos and combine them unless the user requests separate-only output. One section suffices for a short topic. The coordinator—not `study build`—owns orchestration, resumption and acceptance.

## Coordinator: plan once, then delegate by role

Read enough of the whole input to identify conceptual boundaries and dependencies. Ingest slides once with the collection scaffold (it reuses an existing source directory too):

```sh
STUDY=$SKILL/bin/study
$STUDY scaffold collection ip-forwarding --deck path/to/deck.pdf \
  --sections "01-addressing:11-15,02-forwarding:16-24" --deck-title "IP Forwarding" \
  --voice lfm3 lfm3_uk_male_narrator --minutes 12
$STUDY slides lessons/ip-forwarding 11-24 --sheet
$STUDY digest lessons/ip-forwarding
```

Run the digester once per deck after scaffold; complete `source/digest.md` and run `study digest ... --check` before section planning. The command creates one digest entry per slide with extracted text and TODO visual/numbers fields. See [roles.md](roles.md) for capabilities, model mapping, escalation, and the short-lesson rule.

Coordinator owns `brief.md` and `collection.yaml`; scaffold the boilerplate. Group by concept/dependency, not equal page counts. For notes, preserve originals and real heading/line locators.

The brief fixes section order/budgets, voice/quality, notation/colors/examples, term ownership/prerequisites, pronunciation, known source errors and citation conventions (original numbering, labels, added/correction status). Workers define terms in speech and visuals and refresh imported prerequisites; a manifest dependency is not a definition. Allocate the full-lesson budget across sections. Only the first introduces the whole lesson; only the last gives the overall recap. Follow worker-card teaching/speech rules rather than copying them into each prompt.

### Token-efficient dispatch

Keep model reasoning out of long scripted waits; run deterministic production work directly.

1. **Digest once:** cheap vision extraction; verify ambiguous diagrams before planning.
2. **Author:** at most `cpu_slots + 1` planner/animator workers. Stop after reviewed say drafts, frozen scripts and `draft` checkpoints.
3. **Narrate:** after authorization, one background `$STUDY narrate <all sections> --lock $L/tts` process; no worker waiting.
4. **Triage:** inspect real-engine transcripts and semantic/numeric risks before the final render queue; route approved paired script/code fixes by [roles.md](roles.md). Revoice only changed cache blocks.
5. **Render:** script `$STUDY build <section> -q h --cached-only --jobs 2 --frames 4 --lock $L/cpu1 --lock $L/cpu2 --owner <id>` for each section. Spawn a fixer only for actual final-review defects; rerender affected scenes after dependency checks.
6. **Package:** clerk handles validated checkpoints/source-map time ranges; scripts assemble accepted videos.

Use background completion notifications, not polling turns. Keep logs and short summaries rather than dumping whole scene files. Role models, two-way provider fallback and attempt records live only in [roles.md](roles.md).

### Role handoffs

Every handoff states role/section, resolved route, owned paths, source range, budget, required outputs, locks and stopping point. Supply `worker-card.md`, shared brief, assigned inputs and existing checkpoint; do not copy the whole skill or provider policy into worker prompts.

- **Planner:** notes, storyboard and script; verify uncertain slide crops and event traces. No animation code.
- **Animator:** frozen plan/script and reference scene; write code, save early, iterate say drafts. No real-engine TTS/finals unless explicitly assigned.
- **Reviewer:** read-only plan/script/report/sheets/source comparison; return scene, issue and evidence.
- **Clerk:** validated outputs → checkpoint, source times and durable revision; no independent content edits.

Separate planning/animation for large sections; a strong worker may combine them for short lessons. Shared files and combined assembly remain coordinator-owned.

### Final-production preflight

Before TTS, confirm final-stage authorization, released worker ownership, manifest order/count, `status --verify`, `doctor`, disk space, clean script/static checks and each section's exact voice/quality. Resolve factual blockers in speech and visuals together.

Freeze real hashes of scripts/code/specs/notes and shared helpers; check after narration and before each render. Keep logs/state outside the frozen inputs. Stop on drift or failed dependencies; retain good caches/clips. Inspect narration JSON for missing audio, scene errors and proofread flags: exit zero is not a speech-quality pass.

For scripted draft rebuilds, audit inputs, log per-stage exits and skip review after failed builds. Refresh `needs_draft_rebuild` only after fresh frames/interior samples and sync checks—not checkpoint timestamp edits. Final-frame review uses `review -q h --lint --sheet`; adding `--layout` still checks a separate say draft.

## Worker: save a useful checkpoint at every boundary

Apply the main skill's notes → storyboard → scenes → say draft review → narrate → final render
procedure inside the assigned section, using the slot commands above. Use explicit paths, since
nested section IDs are not top-level lesson slugs.

Persist the narration and verified event trace before rendering. Update `checkpoint.yaml`
atomically (write a sibling temporary file, then rename) after each meaningful stage and
before a long tool call. Record actual validated progress, not only an optimistic stage:

```yaml
section_id: 01-addressing
state: ready                 # planned | writing | draft | rendering | review | ready | blocked
completed: [notes, storyboard, code, draft_review, final_render, final_review]
quality: h
voice: {engine: lfm3, preset: lfm3_uk_male_narrator}
input_fingerprint: "sha256 recorded for this section's inputs and render configuration"
scene_progress:
  Classful: {final_render: validated, visual_review: passed}
  Prefixes: {final_render: validated, visual_review: passed}
deliverables_dir: deliverables/r001
last_error: null
next_action: "None; coordinator may assemble this accepted revision."
```

Use real fingerprints, not the descriptive string above. Record hashes of relevant source
inputs, notes/narration, `scenes.py`, `lesson.yaml`, voice reference/configuration, and shared
helpers used, plus engine/dependency versions. Include the source map and shared citation
convention in fingerprints; changed source numbering or provenance may invalidate a render. Save log paths, exact failed command, completed
scene names, and a concrete next action when interrupted. Worker reports should point to
these files; chat summaries alone are insufficient for resumption.

Set `ready` only after validating final streams, dimensions/fps, duration and matching sidecars; review frames, correctness, teaching, speech and citations. Inspect first-use definitions and source changes; record listening/review limitations rather than claiming unperformed checks.

Save actual section-local source times and `sources.md` hash. Copy accepted MP4, sidecars, frozen script/spec/notes and referenced QA reports to a new `deliverables/` revision. Repair relocated relative links or copy their targets, rehash changed sidecars, then atomically update the checkpoint. Preserve earlier revisions until replacement validation. `build/` is a working cache; never accept a say draft or stale file as a real-engine final.

## Resume after lost internet, a failed agent, or a new session

1. Run `$STUDY status <collection|lesson> --verify` (or `--json` for automation) for states,
   output/sidecar validity, hashes, changed-input warnings, cache counts, locks, and exact resume commands.
   Exit codes are 0 all ready, 1 work remains, 2 errors; invalid section YAML is reported without
   hiding other sections. Cache counts are not current-text hits: use `study narrate <section> --check`.
   Locks are inspected read-only; `STALE` means a dead local PID, not permission to delete it blindly.
   Read `collection.yaml`, `brief.md`, and every section checkpoint first. Check for live
   workers before assigning ownership again; never start a duplicate worker for the same path. If none are live but results are missing, inspect the batch manifest and final log entries; an empty live list is not success.
2. Verify accepted revisions and fingerprints. Reuse unchanged, valid `ready` sections.
   Changes invalidate the affected section and any dependent content that relies on them;
   a failed section does not invalidate independent completed sections.
3. Reassign unfinished sections with their files, last error, and next action. Recover from
   the last validated stage, keeping usable code, scene renders, and narration caches.
   A `rendering` checkpoint after a crash is unfinished until its output is checked.
4. For a partially rendered section, verify each existing scene at the intended quality and
   render only missing/invalid scenes using repeated `--scene Name` arguments. Record per-scene
   fingerprints for its code/narration, inputs, configuration, and relevant shared helpers.
   If `scenes.py` changes, do not reuse other scenes solely because they exist: establish that
   their dependencies are unchanged; otherwise treat them as stale and rerender them. Then assemble
   the section without rendering again:

   ```sh
   $STUDY narrate "$COLLECTION/sections/01-addressing" --check   # 100% hits? (writes nothing)
   $STUDY build "$COLLECTION/sections/01-addressing" -q h --cached-only --scene Prefixes --frames 4
   $STUDY build "$COLLECTION/sections/01-addressing" -q h --no-render --frames 4
   ```

   `--no-render` requires all scenes at that quality. It checks existence, not freshness or
   correctness; the coordinator/worker must do those checks. A nonzero render exit may leave
   useful earlier scenes. Do not clear a whole build directory merely to retry one failure.
5. If local content and narration are available, a local render may continue without internet.
   Agent reasoning and externally fetched references may still need connectivity. Do not
   promise background jobs survive a closed harness. On repeated identical failures, save
   the failure and next action, stop that section, and continue independent sections. Report
   completed sections and blockers; never present a partial collection as the full lesson.

## Animation-only preview

Keep section checkpoints at `draft`. Audit exact order/count, input freshness, script/static checks, latest reviews and video/audio streams. Put the preview in `build/draft-preview/`, not final deliverables. Stream-copy only compatible codec/dimensions/fps/time-base/audio formats using ffconcat and ffmetadata; derive chapter/SRT offsets from measured clip durations, renumber cues and reject leaked markup. Verify duration, chapters, streams, full decode, timestamp monotonicity and sampled section order. Save input/output hashes, placeholder voice and review limitations; deliver preview/captions explicitly labeled draft. Do not fabricate final timed sources or mark it ready.

## Combine accepted videos with the existing assembler

Keep each section's MP4 and sidecars, including `sources.md`, as deliverables. Source labels
are baked into the section video and survive concatenation; preserve their original source
identifiers and slide numbers. The coordinator creates a combined `sources.md` by shifting
each section's source-map time ranges by its actual start time in the final video, retaining
section IDs, original locators, and full references. Do not shift source numbers. The existing
assembler does not merge these maps: do this explicitly after assembly, using measured clip
lengths and checking joins. Preserve individual maps and include the combined map in the
accepted combined revision/checkpoint. Any newly rendered introduction or recap also needs
its own citations and mapping. Combine only the manifest's ordered,
accepted revisions, after checking consistent video/audio encoding, resolution, frame rate,
voice, and volume. The current assembler copies video streams, so mismatched video formats
need explicit normalization into new staging copies first. It normalizes audio length per
clip, offsets SRT cues, and generates a new transcript and embedded chapters. Rebuilding the
combined output must not rerender or overwrite accepted section videos. Only the coordinator
may restage or assemble; do not run assembly concurrently with staging changes. Maintain a
collection `assembly-checkpoint.yaml` containing exact ordered section revision paths/hashes and
quality/voice settings and `output: {path: <actual MP4>, sha256: <computed hash>}`. The status reader uses this YAML path, not a similarly named JSON file. Mark it assembling before work, and ready only after validating the
new output and recording its hash; finish with `study status <collection> --verify` reporting exit 0 and ready sections/assembly. Preserve the previously accepted combined video and
sidecars in a durable revision directory outside `combined/build/` until its replacement
passes. An interrupted staging update is unfinished: rerun preflight and restage the entire
manifest before invoking assembly, rather than trusting a leftover staging config.

The recipe below creates a separate staging lesson. Each section MP4 acts as one virtual
scene; `--no-render` means no `scenes.py` or scene classes are needed there. Set `COLLECTION`
to the collection's path, then run from the project root:

```sh
export COLLECTION="${STUDY_HOME:-$HOME/study-videos}/lessons/example"
$SKILL/bin/study python - <<'PY'
import os
from pathlib import Path
import yaml

root = Path(os.environ["COLLECTION"]).resolve()
spec = yaml.safe_load((root / "collection.yaml").read_text())
quality_dirs = {"l": "480p15", "m": "720p30", "h": "1080p30", "h60": "1080p60", "k": "2160p60"}
quality = spec["quality"]
out = root / "combined"
stage = out / "build" / "media" / "videos" / "scenes" / quality_dirs[quality]
# Preflight all sections before changing staging. The review/fingerprint checks above
# are prerequisites; this recipe also rejects missing sidecars and unfinished work.
accepted = []
for part in spec["sections"]:
    folder = root / part["path"]
    check = yaml.safe_load((folder / "checkpoint.yaml").read_text())
    if check["state"] != "ready" or check["quality"] != quality:
        raise RuntimeError(f"Section not accepted at requested quality: {part['id']}")
    deliver = folder / check["deliverables_dir"]
    video = deliver / f"{part['id']}.mp4"
    for path in (video, deliver / "captions.srt", deliver / "transcript.md", deliver / "chapters.txt", deliver / "sources.md"):
        if not path.is_file():
            raise FileNotFoundError(path)
    accepted.append((part, video, deliver / "captions.srt"))
if not accepted:
    raise RuntimeError("No accepted sections")
stage.mkdir(parents=True, exist_ok=True)
scenes = []
for index, (part, video, captions) in enumerate(accepted, 1):
    name = f"Section{index:03d}"
    for src, suffix in ((video, ".mp4"), (captions, ".srt")):
        dst = stage / (name + suffix)
        if dst.is_symlink():
            dst.unlink()
        elif dst.exists():
            raise FileExistsError(f"Refusing to replace a non-link staging file: {dst}")
        dst.symlink_to(src.resolve())
    scenes.append({"name": name, "chapter": part["title"]})
(out / "lesson.yaml").write_text(yaml.safe_dump({
    "title": spec["title"], "voice": spec["voice"], "scenes": scenes,
}, sort_keys=False))
print(f"Staged {len(scenes)} sections at {out}; build with -q {quality} --no-render")
PY
# Use the quality recorded in collection.yaml (h = 1080p30 in this example; sections rendered
# at 1080p60 before the default changed are `h60`: record and combine them as h60).
$SKILL/bin/study build "$COLLECTION/combined" -q h --no-render --frames 4
```

The combined files are `combined/build/combined.mp4`, `captions.srt`, `transcript.md`,
`chapters.txt`. The default combined chapter list has one chapter per section; each original
section video retains its finer scene chapters. To retain every scene chapter in the full
video too, stage the accepted per-scene clips/SRTs as virtual scenes in section/scene order
instead, with unique virtual names and original chapter titles. If this option may be
needed, archive the accepted per-scene MP4/SRT pairs and their order in the section
deliverables; do not rely on disposable build caches. Tell the user whether combined chapters
are per-section or per-scene.

Review every join: order, audio continuity, duplicate introductions, shared example state,
subtitle offsets, chapter timestamps, source labels, and combined source-map time ranges.
Review teaching continuity separately from standalone acceptance: terms must be defined
before use, meanings/pronunciations must agree, and joins or trims must preserve prerequisite
refreshers and natural pauses between ideas. Record this review in the combined checkpoint. Validate the combined MP4 with `ffprobe` and a
full decode check; do not infer successful assembly from an exit code alone (the build tool
can return without assembly when clips are missing). For a stream-copy draft preview with fractional
section joins, decode with `-fps_mode:v passthrough -enc_time_base:v demux` so the null-output test
does not round timestamps to the nominal frame rate and report false duplicate DTS. Separately
verify that the actual MP4 packet DTS values increase strictly; never suppress genuine timestamp
errors. Label any combined `say` preview as a draft and leave final acceptance checkpoints unchanged.
Publish the combined lesson only when
all required sections are ready. If some are unfinished, deliver the completed individual
videos with an explicit status list and exact resume instructions.

Package a compact companion ZIP containing captions, transcript, chapters, timed sources/source-map data, manifests and every referenced speech/visual review report. Generate it after the last report edit and verify members, CRCs and durable video/sidecar hashes. Disclose unresolved ASR flags and missing listening checks; do not relabel them all as formatting. Maintain relative library links without duplicating media.
