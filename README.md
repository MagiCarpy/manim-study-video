# make-study-video

An agent skill and local Python/Manim CLI for turning slides or notes into narrated study videos. Includes planning, animation helpers, speech checks, captions, chapters, sources and section assembly. Independent project; not affiliated with 3Blue1Brown.

## Contents

`SKILL.md` and generation references; `bin/study` and `studio/`; dependency lockfile; configurable voice presets; source-only examples and correctness tests. No credentials, personal lectures, reference recordings, developer telemetry, profiling tools or historical datasets are distributed. The CLI requires no Hermes plugin or developer addon. Agent/provider access is supplied separately by the user.

## Setup (tested on macOS)

```sh
brew install uv ffmpeg cairo pango pkgconf
export SKILL="/path/to/make-study-video"   # your installed checkout
export STUDY="$SKILL/bin/study"
"$STUDY" setup
"$STUDY" doctor
```

The project selects Python 3.12. `say` is the macOS draft voice; other operating systems are not certified by this snapshot. Optional Apple Silicon engines have separate dependencies and large downloads. Review each model's terms before use. Runtime loading is offline; downloading weights requires your explicit choice. See [voices](references/voices.md).

## Local LFM3 narration (recommended final voice)

There is no TTS server URL, port or paid API to connect: the skill loads the model in its own Python process from your local Hugging Face cache. The tested target is Apple Silicon macOS with PyTorch/MPS. The current loader falls back to CPU when MPS is unavailable; other hardware/OS combinations are not certified. No voice-cloning recording is required for LFM3.

### Install the engine dependencies

After the base setup above, run:

```sh
"$STUDY" setup --lfm3
```

This installs the optional Python dependencies, **not the model weights**. Ask your agent to check hardware, free disk/memory and model terms before a large download. The loader executes the checkpoint's custom Python code (`trust_remote_code=True`); only proceed if you trust the pinned upstream checkpoint.

### Reuse your existing local model

The exact model/revision is defined by `LFM3_MODEL` and `LFM3_REVISION` in `studio/tts.py`. A different revision, model variant or a running TTS server is not interchangeable with this adapter. Check the cache without downloading or loading the model:

```sh
"$STUDY" python -c 'from studio.tts import lfm3_model_path; p = lfm3_model_path(); print(p or "Required model revision is not cached"); raise SystemExit(0 if p else 1)'
```

If this prints a snapshot path, skip the download. If your existing cache is elsewhere, set `HF_HOME` to its Hugging Face home directory (or `HF_HUB_CACHE` to its `hub` directory) **before** running any setup/check/download/narration command, and keep the same setting across them. Do not point `HF_HOME` at a single model snapshot. Otherwise keep the normal cache outside this repository. See the upstream [cache environment variables](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables).

### Download the pinned checkpoint

Only if the cache check failed and you approve the download and model terms:

```sh
HF_HUB_OFFLINE=0 "$STUDY" python -c \
'from huggingface_hub import snapshot_download; from studio.tts import LFM3_MODEL, LFM3_REVISION; print(snapshot_download(repo_id=LFM3_MODEL, revision=LFM3_REVISION))'
```

This uses the runtime's pinned revision rather than downloading a floating `main`. The temporary online setting applies only to this download process. If access is denied or authentication/acceptance is required, complete the upstream access flow yourself; never paste a token into the agent conversation or commit one. Do not replace the pinned model/revision just to bypass an error.

Then run `"$STUDY" doctor` and repeat the cache check. Doctor/cache success establishes availability, not successful synthesis; verify a short real LFM3 clip before attempting a lecture. Runtime model loading remains offline and does not fetch missing weights.

### Select the voice and generate

In your lesson's `lesson.yaml`, replace its existing `voice:` setting with this mapping (do not add a duplicate key):

```yaml
voice:
  engine: lfm3
  preset: lfm3_uk_male_narrator
  speed: 1.0
  pause_ms: 350
  lufs: -18
```

The distributed British-male preset uses locale/gender/seed, not a private reference clip. Once the script and say draft are approved:

```sh
LESSON="/absolute/path/to/your/lesson"
"$STUDY" narrate "$LESSON" --check       # read-only coverage; no synthesis
"$STUDY" narrate "$LESSON"               # generates local audio; reuse unchanged blocks
"$STUDY" build "$LESSON" -q h --cached-only --jobs 2
```

Run only one real TTS process at a time; for several sections, pass them together to `narrate` to share one model load. Listen to the output and review timing; a say preview or successful cache lookup is not proof that LFM3 works. Keep weights, generated audio and optional personal recordings out of Git. Further pronunciation, cache and proofreading details: [voices](references/voices.md).

### Copy-paste prompt for your agent

> Set up this checkout's local LFM3 narration using this README and SKILL.md. First inspect the platform, available disk/memory, installed dependencies, and the model ID/revision in studio/tts.py. Explain the model terms and that loading executes pinned upstream Python code; ask my approval before installing packages or downloading weights. Reuse my existing compatible Hugging Face cache if present; otherwise use the exact pinned download command above, outside the repository. Do not connect a paid API, change the pinned model, start a TTS server or silently fall back to say. After setup, run doctor and the offline cache check. Copy examples/hello into a NEW isolated lesson folder without overwriting anything, replace its voice setting with the LFM3 preset above, and synthesize only that short example to verify actual LFM3 output. Probe the real audio and report its path, duration, device and checks actually performed; ask me to listen if you cannot. Do not regenerate existing lectures, download optional Fish/Whisper models, publish anything or add weights/audio/credentials to Git. Stop and report any compatibility or access blocker rather than inventing success.

## Workspace

New lessons default to `~/study-videos/lessons/`, independent of the current directory. `STUDY_HOME` changes the workspace root; explicit lesson paths, `--lessons-dir` and `STUDY_LESSONS_DIR` override it. Existing projects are never moved. Keep sources, cache and accepted revisions together; workspace `library/` and `VIDEO-LIBRARY.md` can index finished videos.

## Small example (no agent or model download)

```sh
mkdir -p "$HOME/study-videos/lessons"
# Copy once into a new folder; do not overwrite an existing lesson.
cp -R "$SKILL/examples/hello" "$HOME/study-videos/lessons/hello"
"$STUDY" build "$HOME/study-videos/lessons/hello" --engine say -q l
"$STUDY" review "$HOME/study-videos/lessons/hello" --lint --layout --sheet
```

This self-authored example uses shapes/text and macOS Samantha. Drafts go into `build/draft/`, not over accepted finals. For actual slides/notes, ask an agent to read [SKILL.md](SKILL.md), supply permitted inputs and specify the requested stage.

## Agent installation and checks

Expose this directory through your agent's supported skill mechanism. Keep one checkout as the source of truth; the CLI locates its own code. No particular username, clone path or Hermes profile is required. Share tracked Git files or a Git-generated archive, not a ZIP of your working directory: ignored local audio and environments may still be present.

```sh
"$STUDY" python -m unittest discover -s "$SKILL/tests" -v
```

Correctness tests do not require rendering a lecture. Do not overwrite accepted projects to validate pipeline changes.

## License status

A redistribution license for this project's own code has **not yet been selected**. Resolve that before calling this a completed open-source release. Dependency/model/asset licenses are separate; see [third-party notes](THIRD_PARTY.md). Setup does not publish or configure a remote repository.
