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
