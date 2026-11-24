# manim-study-video

Turn lecture slides, notes or a topic into narrated Manim study videos with your AI agent. **Designed for a new Mac user who wants Claude Code, Antigravity, Codex or another local agent to download and set everything up.** You do not need an existing TTS installation or Hugging Face experience. Independent project; not affiliated with 3Blue1Brown.

## Start here: ask your agent

Copy this into your agent and replace the URL placeholder with the actual GitHub repository URL from this project's page. Do not guess a repository owner.

```text
Please install and set up manim-study-video from:
PASTE_GITHUB_REPOSITORY_URL_HERE

I am on a Mac and do not have the local TTS model installed. Handle the
setup for me rather than just listing commands. Read the repository's
README.md and SKILL.md, then follow the first-time setup workflow.

Check your local file/terminal access, my Mac's compatibility and available
resources. Choose a skill location supported by the agent I am using, clone
without overwriting anything, and verify the skill can actually be read.
Explain the required installations and large model download in plain English
and ask for my approval before proceeding with those changes. Install only
the base and LFM3 requirements, and download the exact pinned model using
this README. Try anonymous access first; do not assume I need an account.

Finish with a NEW short example using real LFM3 narration, a cached-only
render, and audio/video checks. Show me the resulting video so I can play it.
Do not declare success based only on a say preview or a cache check.
Never request passwords or tokens in chat, overwrite existing projects,
buy API credits, silently switch voices, or publish anything. If you cannot
run local commands or a permission/login requires me, tell me exactly what
to do and wait, then resume from the completed step. Report real results
and blockers honestly.
```

**You only need to:** provide the real URL, approve the explained changes, complete any system permission/login prompts yourself, and play the test video. If your chat app cannot access your Mac's files and terminal, use a local coding/desktop agent or have it guide you through the exact commands one step at a time. An agent's cloud terminal is not your Mac.

## First-time setup workflow for the installing agent

1. **Check capabilities and hardware yourself.** Inspect the local OS/chip, free disk/memory and installed tools; do not ask a beginner to identify them manually when tools can. The tested target is **Apple Silicon macOS**. Intel/CPU fallback is not certified: explain a compatibility blocker and obtain agreement on an alternative rather than promising all Macs work or silently using `say`.
2. **Choose the installation location before creating the Python environment.** Use the native skill locations below, or one user-owned checkout plus a supported registration link. Clone the supplied public GitHub URL, inspect README/SKILL and confirm the expected files. If a destination exists, inspect its origin/state; never overwrite, reset or clean it. Do not move an installed virtual environment just to register a skill.
3. **Get a consolidated installation approval.** Explain native tools, Python packages, the model download (several GB; check current metadata/resources), model terms, and that loading the pinned checkpoint executes upstream Python code (`trust_remote_code=True`). Install only missing approved requirements. Homebrew/Xcode Command Line Tools may require the user to approve a dialog or type a password locally; never ask for that password in chat.
4. **Install base + LFM3 dependencies, then the model.** `setup --lfm3` installs Python libraries **but not the model weights**. Check for the exact cached revision; a miss is expected on a new Mac, not a reason to abandon setup. After approval, use the pinned download command below. Do not download optional Fish/Whisper models or add paid routes. Use the user's existing authorized LLM; role/model suggestions are not extra account requirements.
5. **Verify skill registration.** Follow the actual agent/version's supported discovery mechanism, reload if needed, and confirm it can read this checkout's `SKILL.md`. If discovery is unavailable, open the checkout and explicitly instruct the agent to read it; say that this is manual use, not proven automatic discovery.
6. **Verify real local narration end to end.** Run `doctor --engine lfm3`, then the [safe first LFM3 video check](references/voices.md#first-lfm3-video-check). It creates a unique tiny lesson, generates LFM3 audio, proves current-text cache reuse, renders without synthesis, and checks the resulting streams/decoding. A successful install/cache probe, unit tests or system-voice preview alone is not setup completion.
7. **Hand off something usable.** Report the checkout/skill path, invocation method, model cache location, engine/device, generated video path, checks actually performed and unresolved limitations. Ask the user to play the sample if you cannot listen. Then ask for their slides/notes/topic and desired scope; do not start a full lecture during installation.

## Agent skill locations

Choose **one canonical checkout**; do not install duplicate copies with the same skill name. Confirm current official documentation for the actual product/surface/version before changing registration.

| Agent | Installation/discovery approach |
|---|---|
| Claude Code on this Mac | `~/.claude/skills/manim-study-video/`; an existing checkout can use a supported symlink. Plain Claude chat/cloud sessions are not proof of local terminal access. [Official docs](https://code.claude.com/docs/en/skills). |
| Codex local CLI/IDE | `~/.agents/skills/manim-study-video/`, or the project's `.agents/skills/`; supported symlinks can register an existing checkout. [Official docs](https://developers.openai.com/codex/skills). |
| Antigravity | A workspace's `.agents/skills/manim-study-video/` is the portable project-scope choice. Confirm App/CLI/IDE surface and current personal/global locations rather than guessing; use a real checkout there unless symlink support is verified. Open that workspace and verify discovery. [Official docs](https://antigravity.google/docs/skills). |
| Other local agents | Use their supported skill mechanism; otherwise explicitly read this checkout's `SKILL.md` and execute its workflow. Do not invent native registration commands. |
| Hermes | Add the checkout's parent to the active profile's `skills.external_dirs` using its supported config CLI, preserving existing entries and obtaining approval. Avoid shadow copies. [Official docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills). |

No setup step requires changing `CLAUDE.md`, `AGENTS.md`, existing project rules, unrelated skills or providers. Native skill-file support and local execution are separate capabilities; verify both.

## Setup commands (agent/manual reference)

The following is reference material for the installing agent, not homework for the new user. Set `SKILL` to the actual clone, not the placeholder below. If Homebrew is missing, guide its official installation and any system approvals first.

```sh
export SKILL="/absolute/path/to/manim-study-video"
export STUDY="$SKILL/bin/study"
brew install uv ffmpeg cairo pango pkgconf
"$STUDY" setup --lfm3
```

The project uses Python 3.12. **Hugging Face is the file host for the model download**, not a hosted speech API in this setup. The skill loads the downloaded model inside its own Python process; no TTS server, API key or private voice recording is normally required. Attempt the public checkpoint download anonymously first. If upstream access rules require authentication or acceptance, explain why and let the user complete the official flow locally—never collect credentials in chat. Local TTS does not make the chosen LLM/chat provider itself offline.

Check whether this exact checkpoint is already cached, without loading or downloading it:

```sh
"$STUDY" python -c 'from studio.tts import lfm3_model_path; p = lfm3_model_path(); print(p or "Required model revision is not cached"); raise SystemExit(0 if p else 1)'
```

A new user will normally need the next step. If reusing a nondefault cache, set `HF_HOME` to its Hugging Face home (or `HF_HUB_CACHE` to its hub directory) consistently before checks/downloads/narration, not to an individual snapshot. Keep weights outside the repository. [Cache settings](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables).

### Download the pinned checkpoint

After explicit download/terms approval, run this only when the required revision is missing:

```sh
HF_HUB_OFFLINE=0 "$STUDY" python -c \
'from huggingface_hub import snapshot_download; from studio.tts import LFM3_MODEL, LFM3_REVISION; print(snapshot_download(repo_id=LFM3_MODEL, revision=LFM3_REVISION, token=False))'
```

`token=False` makes this first attempt anonymous, without implicitly sending a saved token. If access is denied specifically because authentication/terms are required, have the user complete the official local flow, then retry with their locally authorized credentials (omit `token=False`); do not create an account or request credentials speculatively. The model ID/revision come from `studio/tts.py`; never replace the pin with a floating `main` to bypass an error. This command permits network access for this download process; normal runtime model loading remains offline. Do not claim the full download or synthesis succeeded from a metadata response alone. On access, disk or compatibility failure, retain progress and explain the exact next action.

```sh
"$STUDY" doctor --engine lfm3
```

Now follow the [first LFM3 video check](references/voices.md#first-lfm3-video-check), not a full lecture. `say` is a fast draft option only; switching final narration away from LFM3 needs the user's agreement. Further voice settings, pronunciation and repairs: [voices](references/voices.md).

## After setup

Ask the agent to use `manim-study-video` with your permitted PDF/PPTX, notes or topic, target duration and requested stage. Automatic delegation is optional; an agent without subagents can do the same roles sequentially. No specific Claude/Codex model ID or extra subscription is required just to install or use the skill.

Projects default to `~/study-videos/lessons/`, with inputs, editable sources, audio cache and accepted revisions together. `STUDY_HOME` changes the workspace; explicit paths, `--lessons-dir` and `STUDY_LESSONS_DIR` override defaults. Never move or overwrite existing lessons without permission. Keep projects/caches outside the code checkout. Final narration is generated with `narrate`, then rendered with `build ... --cached-only`; captions, transcripts, chapters and source maps accompany the video.

## Updates and checks

For a Git clone, inspect `git -C "$SKILL" status --short` first; resolve local edits deliberately without reset/clean. With a clean checkout and configured remote:

```sh
git -C "$SKILL" pull --ff-only
"$STUDY" setup --lfm3
"$STUDY" doctor --engine lfm3
"$STUDY" python -m unittest discover -s "$SKILL/tests" -v
```

A ZIP has no Git remote: install a new source archive into a new directory and intentionally update registration rather than overlaying an existing checkout. New model pins need fresh terms/download approval. Updates do not authorize regenerating existing lectures. Use a known commit/tag with its committed `uv.lock` for reproducibility.

Public CI runs locked base installation, unit tests and a tiny macOS `say` render with strict full decoding; it does not download optional models or use private developer datasets. To run its integration check locally, use a NEW output directory:

```sh
"$STUDY" python "$SKILL/tests/smoke.py" --work-dir "$HOME/study-videos/checks/new-say-smoke"
```

That check validates the base renderer, not LFM3 or listening quality. Fresh base/LFM3 Python environments have been exercised on an existing Mac with installed native tools/cached weights; this is not a new-machine or first-download certification. Hosted Actions execution requires publication and a real run. Other OS/GPU configurations remain uncertified.

## Contents and license

The reusable skill includes source/configuration, dependency lockfile, voice presets, source-only examples and maintained correctness tests—not personal lectures, reference recordings, credentials, generated videos, developer telemetry or historical datasets. No Hermes plugin/developer addon is required. Share tracked Git files or a Git-generated archive, not a ZIP of a working checkout containing ignored local files.

Original code is under the [MIT License](LICENSE), attributed to **manim-study-video contributors**. Dependency, upstream modeling-code/checkpoint and asset terms are separate; see [third-party notes](THIRD_PARTY.md). MIT does not relicense third-party materials or certify compatibility. Installation never publishes or configures a remote for the user's generated videos.
