# Known gotchas
- `pillow<12` is pinned: Manim 0.22's ImageMobject rendering crashes on Pillow 12+.
- SoX isn't installed; `studio` stubs the `sox` module, so manim-voiceover's `global_speed` is
  unsupported — use `rate` (say) or `speed` (fish).
- The 8-bit Fish checkpoint was converted with mlx-audio 0.4; `tts.load_fish` shims the newer
  quantization predicate so it loads with mlx-audio 0.6.x. If a future mlx-audio breaks loading,
  pin `mlx-audio` in pyproject and `$STUDY setup --fish`.
- Fresh parallel builds used to race in manim-voiceover cache-directory creation; `build.py`
  now pre-creates `build/media/voiceovers` before starting `--jobs` renders.
- Each scene renders in its own process, so a render with uncached lines loads the TTS model once
  per such scene and synthesis blocks rendering. Run `study narrate` first: one load, then renders
  hit the cache (`--cached-only` proves it). Fish memory peak ≈ 6.4 GB RSS; LFM3 ≈ 4.2 GB.
- **Run at most one TTS model process at a time** (fish or lfm3, never both, never two of one):
  they share unified memory/GPU and the machine lags badly. Two concurrent Fish processes were
  not validated for this reason; treat TTS concurrency as 1.
- LFM3 needs torch in the skill venv (`study setup --lfm3`); it resolves alongside mlx-audio and
  manim without changing their pinned versions (shared transformers 5.21). The harmless
  "causal_conv1d … falling back" / "Redirects are not supported" warnings come from CUDA-only kernels.
- PPTX images need Keynote or headless LibreOffice; if both fail, ask for a PDF.
- `uv run` from inside `$SKILL` is fine, but prefer `$STUDY` so `PYTHONPATH`/cwd handling is right.
