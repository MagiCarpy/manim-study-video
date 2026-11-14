# Voices and setup

Load only for engine setup, presets, pronunciation or audio repairs. `$SKILL` is the installed skill directory; `STUDY="$SKILL/bin/study"`.

## Setup (tested on macOS)

```sh
brew install uv ffmpeg cairo pango pkgconf
"$STUDY" setup
"$STUDY" doctor
```

Optional engines require additional packages and large upstream models. Ask before installing/downloading anything; `uv.lock` records the supported dependency set. Runtime loading is offline and never fetches missing weights. Model licenses are separate from code and may restrict usage: read the terms distributed with the exact checkpoint before use. No model weights, platform fonts or reference recordings are bundled.

- `"$STUDY" setup --lfm3`: installs PyTorch/Transformers dependencies, not weights. Follow [README local LFM3 setup](../README.md#local-lfm3-narration-recommended-final-voice) for existing-cache detection, the explicit pinned download, and a copy-paste agent setup prompt. Production default is `lfm3_uk_male_narrator`.
- `"$STUDY" setup --fish`: optional Apple Silicon Fish/MLX support; requires an authorized reference clip/preset.
- `"$STUDY" setup --proofread`: optional Apple Silicon Whisper proofreading. `study narrate` uses it when installed; `study voice proofread <lesson>` rechecks existing audio.
- `say`: macOS system voice for fast drafts, no model download. Use `say -v '?'` to list installed voices. It is not a silent replacement for final LFM3 audio.

Model IDs/revisions and cache checks are defined in `studio/tts.py`; use `doctor --engine lfm3` to require LFM3 availability (no synthesis). Keep weights in the normal model cache, never the repository. Other operating systems and hardware require their own compatibility checks; optional MLX dependencies are Apple Silicon-specific.

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
