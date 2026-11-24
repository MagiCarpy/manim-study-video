# Voices and setup

Load only for engine setup, presets, pronunciation or audio repairs. `$SKILL` is the installed skill directory; `STUDY="$SKILL/bin/study"`.

## Setup (tested on macOS)

```sh
brew install uv ffmpeg cairo pango pkgconf
"$STUDY" setup
"$STUDY" doctor
```

Optional engines require additional packages and large upstream models. Ask before installing/downloading anything; `uv.lock` records the supported dependency set. Runtime loading is offline and never fetches missing weights. Model licenses are separate from code and may restrict usage: read the terms distributed with the exact checkpoint before use. No model weights, platform fonts or reference recordings are bundled.

- `"$STUDY" setup --lfm3`: installs PyTorch/Transformers dependencies, not weights. Start with [README beginner onboarding](../README.md#start-here-ask-your-agent), including approval, anonymous-first access and the exact pinned download. A new user is not expected to know Hugging Face or preinstall a model. Production default is `lfm3_uk_male_narrator`.
- `"$STUDY" setup --fish`: optional Apple Silicon Fish/MLX support; requires an authorized reference clip/preset.
- `"$STUDY" setup --proofread`: optional Apple Silicon Whisper proofreading. `study narrate` uses it when installed; `study voice proofread <lesson>` rechecks existing audio.
- `say`: macOS system voice for fast drafts, no model download. Use `say -v '?'` to list installed voices. It is not a silent replacement for final LFM3 audio.

Resolve the model ID and pinned revision from `studio/tts.py` for cache probes, downloads and recovery messages; downloading a floating default revision can leave the offline loader unable to find its required checkpoint. Use `doctor --engine lfm3` to require availability, then validate actual short LFM3 synthesis and CLI `narrate` followed by `narrate --check`; dependency/cache checks and a say preview do not prove the real engine works. Require current-text cache hits with no synthesis on the check. Keep weights in the normal model cache, never the repository. Distinguish a fresh Python environment reusing native tools/model cache from a new machine or first-download test, and disclose untested listening/hardware/access paths. Other operating systems and hardware require their own compatibility checks; optional MLX dependencies are Apple Silicon-specific.

## First LFM3 video check

For the installing agent after approved dependency/model setup: run this as one shell block with `STUDY` set to the actual installed CLI. It creates a unique lesson under the configured lessons directory, copies only the three source files from the tiny example, and explicitly selects LFM3. It never overwrites an existing lesson or uses a personal lecture. This is a setup check, not permission to generate a full course video.

<!-- first-lfm3-bootstrap:start -->
```sh
set -eu
LESSON=$("$STUDY" python - <<'PY'
from pathlib import Path
import shutil
import tempfile
import yaml
from studio.paths import SKILL_DIR, lessons_dir
root = lessons_dir()
root.mkdir(parents=True, exist_ok=True)
lesson = Path(tempfile.mkdtemp(prefix="setup-check-", dir=root))
for name in ("lesson.yaml", "script.md", "scenes.py"):
    shutil.copy2(SKILL_DIR / "examples" / "hello" / name, lesson / name)
p = lesson / "lesson.yaml"
config = yaml.safe_load(p.read_text())
config["voice"] = {"engine": "lfm3", "preset": "lfm3_uk_male_narrator"}
config.pop("rate", None)
p.write_text(yaml.safe_dump(config, sort_keys=False))
print(lesson)
PY
)
"$STUDY" narrate "$LESSON"
"$STUDY" narrate "$LESSON" --check
"$STUDY" build "$LESSON" -q l --cached-only --jobs 1
"$STUDY" review "$LESSON" --lint --sheet
VIDEO="$LESSON/build/draft/${LESSON##*/}.mp4"
ffprobe -v error -show_streams -show_format -of json "$VIDEO"
ffmpeg -v error -xerror -i "$VIDEO" -f null -
printf 'Play this setup sample: %s\n' "$VIDEO"
```
<!-- first-lfm3-bootstrap:end -->

Require actual LFM3 synthesis in the first narration log, then **all current-text cache hits, zero synthesis and zero missing lines** in `narrate --check`. Inspect ffprobe's JSON for both video and audio streams and a positive, short duration within the two-minute fixture budget; require the strict decoder to exit successfully. If any step fails, report its real failure and resume after fixing it, not from an empty new install or a system-voice substitution. Record the actual paths/output rather than predicting them. The assembler names the output after the lesson directory, not the copied YAML slug: this low-quality test writes `build/draft/<unique-lesson-directory>.mp4`, not over a final.

Ask the user to play this video. If listening is unavailable, say that decoding/stream checks passed but voice naturalness and pronunciation were not heard. Installation checks do not certify teaching quality. Report skill registration/manual invocation, engine/preset/device, model cache, video path and remaining blockers. The user should not need to understand model caches to use the resulting skill.

## Select a voice

```yaml
voice: Samantha
rate: 175
# Production default:
voice:
  engine: lfm3
  preset: lfm3_uk_male_narrator
  speed: 1.0
  pause_ms: 350
  lufs: -18
# Or an authorized Fish reference (relative to the lesson):
voice:
  engine: fish
  ref_audio: voice/reference.wav
  ref_text: "Exact words spoken in the reference clip."
  seed: 0
```

Choose one of the voice blocks, not all of them. `--engine X` uses that engine's own defaults; presets belong to their engine. LFM3 presets contain locale, gender and seed; the default remains British male, seed 4. LFM3 does not use the Fish reference-cloning interface. Preserve the seed per spoken part for consistency and audition/listen before selecting a different voice.

Fish requires a reference for consistent narration. Supply matching `ref_audio`/`ref_text`, or create a preset using `study voice audition` and `study voice save`. A fixed seed without a reference does not guarantee one speaker across different lines. No private reference recording is included in the public package. Keep any local recordings/transcripts out of Git.

```sh
"$STUDY" voice audition --n 4
# Listen to the generated audition paths printed by the command.
"$STUDY" voice save narrator <authorized-reference.wav> --text "Exact spoken transcript" --force
```

Use only a voice you have permission to use. Reference pace/energy affect the result. Avoid unsupported style instructions: some local engines may speak them literally. Preset recordings and generated auditions are local files, not release assets.

## Cache, timing and speech checks

- Voice parameters, spoken text and reference-content hash participate in audio caching. Unchanged blocks reuse audio; changing voice/text requires new audio and refreshed affected renders. Use `narrate --check` for current-text coverage, not cache entry counts.
- Iterate visuals with `--engine say`, then freeze speech, narrate sections in one process and render `--cached-only`. Never overwrite final audio with a draft engine. Keep one TTS model process; parallel synthesis is not assumed safe.
- Keep voiceover blocks within the script limits. Short blocks make targeted repairs possible; do not lower a global generation cap as a substitute for natural-boundary splits.
- `[[slnc 400]]` requests 400 ms of silence. LFM3 substitutes silence for `[pause]`; Fish interprets supported inline tags. Strip markup from screen text, captions and transcripts. Validate pauses with real-engine audio, not a say draft.
- Keep canonical spelling in scripts/captions. `tts.PRONOUNCE`, lesson `pronounce:` entries and `tts.spoken_text` apply audio-only spoken forms for acronyms, device names, addresses and numbers. Avoid raw symbolic shorthand or fragile repeated-digit runs in speech.
- Check numerical examples against the full ASR transcript, not only flags: a repeated bit may be omitted without being flagged. When supported by the verified example, say “four ones” or “one followed by three zeros” while keeping the visible bit string unchanged.
- Normalize obvious punctuation, currency and ordinal formatting mechanically. Escalate uncertain bits, symbols, negation, names, acronyms and recipient relationships. ASR is not a listening check; disclose missing listening or unresolved flags.
- Planner/coordinator approves changes; update script/code together, preserving pauses, beats and bookmarks. Regenerate only changed blocks, rerender affected scenes and refresh timing/source maps after verifying other inputs remain unchanged.

## LFM3 respellings and proofread lessons

Observed on a 48-minute networking lecture (`lfm3_uk_male_narrator`). Apply these from planning onward; they are audio-only, so captions keep the written form.

- **Scaffolded defaults** (`studio/scaffold.py` `DEFAULT_PRONOUNCE`, written into every new `lesson.yaml`): `Go-Back-N` → `go-back-en` (the final N was dropped, and plain `go back en` still lost it at sentence end); bare `y` → `why` (it was voiced "yay" or "lie", or dropped). Keep them; add deck-specific entries beside them.
- **No sentence-initial spelled acronyms.** The rule applies to every sentence, not only a block's first word. All four LFM3 misreadings of `TCP` ("tay cp", "dcp", "ctp") were sentence-initial, while mid-sentence `T C P` was fine. Reword ("Then TCP sends…"), or respell that line `Tee see pee`.
- **Dotted addresses with repeated octets** such as `130.1.1.1` gained an extra "one". Add a per-address entry with comma pauses, e.g. `"130.1.1.1": "one thirty, dot one, dot one, dot one"`.
- **Re-voice one line only:** add a phrase-level `pronounce:` key that occurs only in that line, e.g. `"TCP adopted it": "Tee see pee adopted it"`. Keys match the text after bookmarks are removed but before `[pause]` is split out, so a key must not span `[pause]` or `<bookmark/>`. Before narrating, run `narrate --check` and confirm `missing` equals the number of lines you meant to change.
- **LFM3 is seeded** (default `seed: 0`), so re-narrating unchanged text does not resample it. To resample a swapped word (it said "takes" for "picks", then "clicks"), change the spoken text minimally with a homophone respelling (`pix`) instead of rewording the caption.
- **Usually ASR noise, not speech errors** (confirm by listening when you can): hi/high, mail/male, why/y, too/two, end/n, bytes/bites, Martha/"Marfa" (British accent), and the letter N heard as "in" or "and".
- **Pacing:** the same script runs ~17% longer in LFM3 than in `say` (42.2 vs 36.1 min). Budget planning words at about 150 per minute.
