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

Then run `"$STUDY" doctor --engine lfm3` and repeat the cache check. Doctor/cache success establishes availability, not successful synthesis; verify a short real LFM3 clip before attempting a lecture. Runtime model loading remains offline and does not fetch missing weights.

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

> Set up this checkout's local LFM3 narration using this README and SKILL.md. First inspect the platform, available disk/memory, installed dependencies, and the model ID/revision in studio/tts.py. Explain the model terms and that loading executes pinned upstream Python code; ask my approval before installing packages or downloading weights. Reuse my existing compatible Hugging Face cache if present; otherwise use the exact pinned download command above, outside the repository. Do not connect a paid API, change the pinned model, start a TTS server or silently fall back to say. After setup, run doctor --engine lfm3 and the offline cache check. Copy examples/hello into a NEW isolated lesson folder without overwriting anything, replace its voice setting with the LFM3 preset above, and synthesize only that short example to verify actual LFM3 output. Probe the real audio and report its path, duration, device and checks actually performed; ask me to listen if you cannot. Do not regenerate existing lectures, download optional Fish/Whisper models, publish anything or add weights/audio/credentials to Git. Stop and report any compatibility or access blocker rather than inventing success.

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

Keep one checkout as the source of truth; `$SKILL` must be its absolute path. The CLI locates its own code. Choose one discovery method; do not install duplicate copies with the same skill name.

**Any file-capable agent:** open the checkout as your working folder and ask: “Read SKILL.md in this checkout, follow its linked references only when needed, and help me complete the README setup. Use my existing authorized model connection; do not change providers or buy credits.” This works without automatic skill discovery.

**Codex / Claude Code:** both support symlinked skill directories. Choose the relevant user-level skills directory below, then register the existing checkout without overwriting anything:

```sh
SKILLS_DIR="$HOME/.agents/skills"       # Codex
# SKILLS_DIR="$HOME/.claude/skills"     # Claude Code: use this instead
DEST="$SKILLS_DIR/make-study-video"
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  printf 'Already exists: %s; inspect it instead of overwriting.\n' "$DEST"
else
  mkdir -p "$SKILLS_DIR"
  ln -s "$SKILL" "$DEST"
fi
```

Restart/reload the agent if necessary and explicitly request `make-study-video`; verify it reads this checkout's SKILL.md. Upstream discovery rules: [Codex](https://developers.openai.com/codex/skills), [Claude Code](https://code.claude.com/docs/en/skills).

**Hermes:** ask its agent to add the parent of this checkout to `skills.external_dirs` for the active profile using `hermes config set`, preserving existing entries and asking approval before changing configuration. For example, a checkout at `~/agent-skills/make-study-video` uses `~/agent-skills` as its discovery root. Do not overwrite config.yaml or create a shadow copy; confirm the loaded skill path with `skill_view`. [Hermes shared-skill discovery](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).

Model/provider authentication is separate from TTS setup. Use your agent's own sign-in flow; do not put credentials in this repo or assume every model named in the role table is available to your account.

No particular username, clone path or Hermes profile is required. Share tracked Git files or a Git-generated archive, not a ZIP of your working directory: ignored local audio and environments may still be present.

```sh
"$STUDY" python -m unittest discover -s "$SKILL/tests" -v
```

Correctness tests do not require rendering a lecture. Do not overwrite accepted projects to validate pipeline changes.

## Updates and releases

For a Git clone, inspect `git -C "$SKILL" status --short` first. If it has local edits, resolve them deliberately before updating; never use reset/clean to erase them. With a clean checkout and a configured remote:

```sh
git -C "$SKILL" pull --ff-only
"$STUDY" setup --lfm3              # or setup without extras if you only use say
"$STUDY" doctor --engine lfm3      # or --engine say
"$STUDY" python -m unittest discover -s "$SKILL/tests" -v
git -C "$SKILL" rev-parse HEAD     # record the generation-code revision
```

A ZIP download has no Git remote: get a new source archive and install it into a new directory, then intentionally update your skill registration. Do not overlay or delete an old working checkout. Keep projects/caches outside the code checkout. Updates do not authorize re-narrating or re-rendering existing projects; if the pinned model changes, review terms and approve the new download explicitly. For reproducibility, use a known commit/tag with its committed `uv.lock`; do not upgrade dependencies independently to fix an unexplained failure.

## Automated checks

The GitHub Actions workflow runs locked base installation, public unit tests, and a tiny macOS say render with lint and full audio/video decode. It has read-only repository permissions, does not install optional TTS models and does not use private benchmark data. It runs on pushes, pull requests and manual dispatch after you publish the repository; merely adding the workflow does not mean a hosted run has passed.

Run the same integration check locally in a NEW isolated output directory (the command refuses an existing directory):

```sh
"$STUDY" python "$SKILL/tests/smoke.py" --work-dir "$HOME/study-videos/checks/new-say-smoke"
```

`doctor --engine lfm3` makes missing LFM3 dependencies/cache a failure rather than an optional warning; repeat `--engine` to require several engines. Doctor does not load/synthesize a model, certify audio quality or guarantee hardware capacity. The smoke check uses say; separately validate one short real LFM3 example before a long project. This snapshot was exercised in fresh base-only and LFM3 Python environments on an existing Mac, reusing installed native tools and the pinned model cache; that is not a new-machine or first-download certification. Hosted Actions execution still requires publication. Support target remains macOS; other OS/GPU combinations are not certified.

## License status

This project's original code is distributed under the [MIT License](LICENSE), attributed to **make-study-video contributors**. Dependency, upstream modeling-code/checkpoint and asset licenses remain separate; see [third-party notes](THIRD_PARTY.md). MIT does not relicense third-party materials or certify their compatibility for your use/distribution. Setup does not publish or configure a remote repository.
