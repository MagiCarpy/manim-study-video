"""Offline narration engines plugged into manim-voiceover.

Usage inside a scene (StudyScene sets this up for you):

    with self.voiceover(text="The client sends a SYN.") as tracker:
        self.play(..., run_time=tracker.duration)

Engines (chosen by lesson.yaml `voice:`; build.py passes it as JSON in $STUDIO_TTS):

    voice: Samantha                 # shorthand for engine say (+ top-level `rate:`)
    voice: {engine: say, name: Samantha, rate: 175}
    voice: {engine: fish, preset: narrator}          # same speaker for every line
    voice: {engine: lfm3, preset: lfm3_us_female}    # or locale: en-US, gender: female, seed: N
    voice: {engine: fish, speed: 1.0, temperature: 0.7, top_p: 0.7, seed: 0,
            ref_audio: voice/me.wav, ref_text: "exact words in the clip",
            instruct: "warm, friendly teacher"}

`say`  macOS built-in, instant, robotic. Embedded commands like "[[slnc 300]]"
       (300 ms pause) work.
`lfm3` LiquidAI LFM3-Audio-2B via transformers/PyTorch on MPS (`--extra lfm3`),
       pinned revision, offline HF cache. ~0.56 s compute per audio-second. No
       cloning: a voice is locale + gender + seed (`preset: lfm3_us_female`, see
       voices/lfm3_*.yaml); the seed is re-applied for every part so a lesson keeps
       one speaker. "[pause]" and other Fish tags become `pause_ms` of silence;
       every clip is loudness-normalized (-18 LUFS, true peak <= -1.5 dBTP).
`fish` Fish Audio S2 Pro via mlx-audio (Apple Silicon, `--extra fish`), loaded
       from the Hugging Face cache with HF_HUB_OFFLINE=1 (never downloads).
       "[[slnc N]]" becomes exact silence; Fish inline tags like "[pause]" or
       "[excited]" are passed through (and stripped for `say` and captions).
       Fish always clones a reference clip: `ref_audio`/`ref_text` if given, else
       the voice preset `preset:` (default "narrator", see studio/voices.py).
       Without one it would invent a new speaker for every line/part.

Every engine parameter is part of the manim-voiceover cache key, so changing
voice settings re-synthesizes and unchanged lines are reused. The reference clip
is keyed by content (`ref_sha1`) + `ref_text`, not by its path, so moving the
skill or the lesson keeps the cache valid (older entries that still carry a
`ref_audio` path match too). Cache hits are not re-appended to cache.json, and
new entries are appended under a file lock (parallel renders share the cache).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from manim_voiceover.defaults import DEFAULT_VOICEOVER_CACHE_JSON_FILENAME
from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService, initialize_speech_service
from manim_voiceover.services.cache import (load_voiceover_cache, parse_voiceover_cache_entry,
                                            serialize_voiceover_cache_entry,
                                            serialize_voiceover_input_data)

DEFAULT_VOICE = "Samantha"
DEFAULT_RATE = 175  # words per minute
DEFAULT_LFM3_PRESET = "lfm3_uk_male_narrator"  # voices/<name>.yaml; user-chosen British male (seed 4)
FISH_MODEL = "mlx-community/fish-audio-s2-pro-8bit"
FISH_MAX_TOKENS = 2048  # codec frames per text part (21.5/s -> ~95 s); mlx-audio's default 1024 cuts at ~47 s

# Audio-only pronunciation fixes for CS jargon (captions keep the original).
# Extend freely. Keys are matched as whole words, case-sensitive.
PRONOUNCE = {
    "SYN-ACK": "sin ack",
    "SYN": "sin",
    "ACK": "ack",
    "FIN": "fin",
    "RTT": "R T T",
    "TCP": "T C P",
    "UDP": "U D P",
    "DNS": "D N S",
    "TLB": "T L B",
    "CPU": "C P U",
    "OS": "O S",
    "I/O": "I O",
    "RR": "round robin",
    "FCFS": "first come first served",
    "SJF": "shortest job first",
    "cwnd": "congestion window",
    "ssthresh": "slow start threshold",
    "TCAMs": "tee-cams",
    "TCAM": "tee-cam",
    "CIDR": "cider",
    "NAT": "nat",
    "ARP": "arp",
    "DHCP": "D H C P",
    "ICMP": "I C M P",
    "MTU": "M T U",
    "ACLs": "A C Ls",
    "ACL": "A C L",
    "IPs": "I Ps",
    "IP": "I P",
    "IPv4": "I P v four",
    "IPv6": "I P v six",
    "LAN": "lan",
    "LANs": "lans",
    "ISPs": "I S Ps",
    "ISP": "I S P",
    "POPs": "pops",
    "POP": "pop",
    "NAPs": "naps",
    "NAP": "nap",
    "ARPANET": "arpa net",
    "NSFNET": "N S F net",
    "MILNET": "mil net",
    "MAC": "mack",
    "MACs": "macks",
    "ARPs": "arp messages",  # noun only: write "sends an ARP request", not "E1 ARPs for E2" (misread)
    "CAMs": "cams",
    "CAM": "cam",
    "TTL": "T T L",
    "MF": "M F",
    "DF": "D F",
    "UCLA": "U C L A",
    "e.g.": "for example",
    "i.e.": "that is",
    "vs.": "versus",
    "vs": "versus",
    "BGP": "B G P",
    "OSPF": "O S P F",
    "RIP": "rip",
    "IGRP": "I G R P",
    "LSPs": "L S Ps",
    "LSP": "L S P",
    "ECMP": "E C M P",
    "SDN": "ess dee en",
    "ASIC": "A-sick",
    "ASICs": "A-sicks",
    "ECE": "E C E",
}

# Frozen copy of PRONOUNCE as of 2026-10-29 (do not edit): narration cached before then was
# voiced with exactly these rules, so cache keys only add the spoken text when today's rules
# (PRONOUNCE, lesson `pronounce:`, identifiers, numbers) say a line differently. Edit PRONOUNCE.
_PRONOUNCE_V1 = {
    'SYN-ACK': 'sin ack', 'SYN': 'sin', 'ACK': 'ack', 'FIN': 'fin', 'RTT': 'R T T', 'TCP': 'T C P',
    'UDP': 'U D P', 'DNS': 'D N S', 'TLB': 'T L B', 'CPU': 'C P U', 'OS': 'O S', 'I/O': 'I O',
    'RR': 'round robin', 'FCFS': 'first come first served', 'SJF': 'shortest job first',
    'cwnd': 'congestion window', 'ssthresh': 'slow start threshold', 'TCAMs': 'tee-cams',
    'TCAM': 'tee-cam', 'CIDR': 'cider', 'NAT': 'nat', 'ARP': 'arp', 'DHCP': 'D H C P', 'ICMP': 'I C M P',
    'MTU': 'M T U', 'ACLs': 'A C Ls', 'ACL': 'A C L', 'IPs': 'I Ps', 'IP': 'I P', 'IPv4': 'I P v four',
    'IPv6': 'I P v six', 'LAN': 'lan', 'LANs': 'lans', 'ISPs': 'I S Ps', 'ISP': 'I S P', 'POPs': 'pops',
    'POP': 'pop', 'NAPs': 'naps', 'NAP': 'nap', 'ARPANET': 'arpa net', 'NSFNET': 'N S F net',
    'MILNET': 'mil net',
}

# Per-lesson additions from lesson.yaml `pronounce:` (set by make_service; one lesson per process).
LESSON_PRONOUNCE: dict[str, str] = {}

# Letter+digit identifiers (R1, P4, E12, MP3) are read as symbols: "R one", "P four".
# Without this the voice may read "R1" as one word ("raw one").
_IDENT = re.compile(r"(?<![\w-])([A-Z]{1,3})(\d{1,4})(?![\w-])")
# Lowercase interface-style names (eth1, wlan0): the word, then the number ("eth one").
_IFACE = re.compile(r"(?<![\w-])([a-z]{2,5})(\d{1,3})(?![\w-])")
# Dotted IPv4 address with optional prefix length: 128.32.0.0/16.
_ADDR = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?:/(\d{1,2}))?(?!\w|\.\d)")
# Bare prefix length after a space, start, or bracket: "a /24 entry".
_PREFIX = re.compile(r"(?<![\w/.])/(\d{1,3})(?![\w/])")
# Number range with an en dash: 1–15 (hyphens read as minus and em dashes as pauses, so left alone).
_RANGE = re.compile(r"(?<![\w.])(\d+)\s?–\s?(\d+)(?![\w.])")
# Any other written number. LFM3 misreads digits badly (31 -> "thirteen", 1500 -> "fifty pounded",
# 64 -> "six or four"; measured 2026-10-29), so every number is spoken as words.
_DECIMAL = re.compile(r"(?<![\w.,])(\d+)\.(\d+)(?![\w]|\.\d)")
_NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d{1,6})(%?)(?![\w]|[.,]\d)")
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: int) -> str:
    """0..999999999 -> English words ("one hundred twenty-eight")."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return _ONES[n // 100] + " hundred" + (" " + number_words(n % 100) if n % 100 else "")
    if n < 1_000_000:
        return number_words(n // 1000) + " thousand" + (" " + number_words(n % 1000) if n % 1000 else "")
    return number_words(n // 1_000_000) + " million" + (" " + number_words(n % 1_000_000) if n % 1_000_000 else "")


def spoken_number(n: int) -> str:
    """Numbers as people say them: 1480 "fourteen eighty", 1500 "fifteen hundred", 1981 "nineteen
    eighty-one"; 2026, 1000 and the rest via number_words ("two thousand twenty-six")."""
    hi, lo = divmod(n, 100)
    if 1010 <= n <= 1999 and lo:
        return number_words(hi) + (" oh " + _ONES[lo] if lo < 10 else " " + number_words(lo))
    if 1100 <= n <= 9900 and not lo and n % 1000:
        return number_words(hi) + " hundred"
    return number_words(n)


def octet_words(n: int) -> str:
    """Address octets the way network people say them: 128 "one twenty-eight", 105 "one oh five"."""
    if n < 100 or n % 100 == 0:
        return number_words(n)
    rest = n % 100
    return _ONES[n // 100] + " " + ("oh " + _ONES[rest] if rest < 10 else number_words(rest))


# Letter spellings the narrator voice gets right where the bare capital fails (LFM3 UK male,
# Whisper-checked 2026-10-29: "R one" -> "Ra-1"/"raw", "P one" -> "Par1"; "Ar one", "Pee one" clean).
_LETTER_SAY = {"R": "Ar", "P": "Pee"}
_IFACE_SAY = {"eth": "E T H"}
# The same letters when a script already spells the number out ("R one", "P two").
_LETTER_WORD = re.compile(r"(?<![\w'-])([RP])(?=[ -](?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
                          r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b)")  # "eth one" -> "F1"; spelled letters clean


def _ident(m: re.Match) -> str:
    digits = m.group(2)
    num = number_words(int(digits)) if not digits.startswith("0") or digits == "0" else \
        " ".join(_ONES[int(d)] for d in digits)
    return " ".join(_LETTER_SAY.get(c, c) for c in m.group(1)) + " " + num


def _addr(m: re.Match) -> str:
    octets = [int(o) for o in m.group(1).split(".")]
    if any(o > 255 for o in octets):
        return m.group(0)  # a version number or similar, not an address
    said = " dot ".join(octet_words(o) for o in octets)
    return said + (" slash " + number_words(int(m.group(2))) if m.group(2) else "")


def _respell(text: str, table: dict) -> str:
    for word in sorted(table, key=len, reverse=True):
        text = re.sub(rf"(?<![\w-]){re.escape(word)}(?![\w-])", table[word], text)
    return text


_SAY_CMD = re.compile(r"\[\[.*?\]\]")
_SLNC = re.compile(r"\[\[\s*slnc\s+(\d+)\s*\]\]")
_TAG = re.compile(r"(?<!\[)\[[^\[\]]+\](?!\])")  # Fish inline tag: [pause], [excited], ...


def caption_text(text: str) -> str:
    """Narration text as it should appear in captions/transcripts."""
    return " ".join(_TAG.sub("", _SAY_CMD.sub("", remove_bookmarks(text))).split())


def spoken_text(text: str) -> str:
    """Narration as the voice reads it: respellings, then letter+digit names, addresses, prefixes, ranges.
    Captions keep the written form (caption_text)."""
    text = _respell(remove_bookmarks(text), {**PRONOUNCE, **LESSON_PRONOUNCE})
    text = _ADDR.sub(_addr, text)
    text = _PREFIX.sub(lambda m: "slash " + number_words(int(m.group(1))), text)
    text = _RANGE.sub(lambda m: f"{spoken_number(int(m.group(1)))} to {spoken_number(int(m.group(2)))}", text)
    text = _IDENT.sub(_ident, text)
    text = _LETTER_WORD.sub(lambda m: _LETTER_SAY[m.group(1)], text)
    text = re.sub(r"(?<![\w'’&-])R(?=['’]s\b|(?![\w'’&-]))", "Ar", text)  # a router named just "R" ("R keeps" -> "Ra keeps")
    text = _IFACE.sub(lambda m: f"{_IFACE_SAY.get(m.group(1), m.group(1))} {number_words(int(m.group(2)))}", text)
    text = _DECIMAL.sub(lambda m: number_words(int(m.group(1))) + " point " + " ".join(_ONES[int(d)] for d in m.group(2)), text)
    return _NUMBER.sub(lambda m: spoken_number(int(m.group(1).replace(",", ""))) + (" percent" if m.group(2) else ""), text)


def _legacy_spoken_text(text: str) -> str:
    return _respell(remove_bookmarks(text), _PRONOUNCE_V1)


def _to_wav(src: Path, out_wav: Path, tempo: float = 1.0) -> None:
    """Any audio -> 44.1 kHz mono WAV; `tempo` changes speed without changing pitch."""
    af = ["-af", f"atempo={tempo:.4f}"] if abs(tempo - 1.0) > 1e-3 else []
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), *af,
                    "-ar", "44100", "-ac", "1", str(out_wav)], check=True)


def synthesize(text: str, out_wav: Path, voice: str | None = None, rate: int | None = None) -> Path:
    """Render `text` to a 44.1 kHz mono WAV with `say` + ffmpeg."""
    voice = voice or DEFAULT_VOICE
    rate = int(rate or DEFAULT_RATE)
    if not shutil.which("say"):
        raise RuntimeError("macOS `say` not found; use another engine (voice: {engine: fish}).")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        txt, aiff = Path(tmp) / "in.txt", Path(tmp) / "out.aiff"
        txt.write_text(_TAG.sub("", spoken_text(text)), encoding="utf-8")
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-f", str(txt), "-o", str(aiff)], check=True)
        _to_wav(aiff, out_wav)
    return out_wav


def approx_word_boundaries(text: str, wav: Path) -> list[dict]:
    """Local engines give no timings; assume time is proportional to characters.
    Good enough for `wait_until_bookmark` (typically within ~0.3 s)."""
    from manim_voiceover.modify_audio import get_duration
    from manim_voiceover.tracker import AUDIO_OFFSET_RESOLUTION

    duration = get_duration(wav)
    n = max(len(text), 1)
    out = []
    for m in re.finditer(r"\S+", text):
        out.append({
            "audio_offset": int(duration * m.start() / n * AUDIO_OFFSET_RESOLUTION),
            "text_offset": m.start(),
            "word_length": len(m.group()),
            "text": m.group(),
            "boundary_type": "Word",
        })
    out.append({
        "audio_offset": int(duration * AUDIO_OFFSET_RESOLUTION),
        "text_offset": n, "word_length": 1, "text": ".", "boundary_type": "Word",
    })
    return out


# Keys ignored when matching cache entries: the reference clip's path (legacy fish
# entries); its content hash `ref_sha1` and `ref_text` stay in the key.
_KEY_IGNORE = ("ref_audio",)


def _match_key(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in _KEY_IGNORE} if "ref_sha1" in data else dict(data)


def _write_json_atomic(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


class _LocalService(SpeechService):
    """Shared caching logic: subclasses define `params` and `_synthesize`."""

    engine = ""
    params: dict = {}

    def cache_input_data(self, text: str) -> dict:
        """The manim-voiceover cache key for `text` (as the scene passes it to voiceover())."""
        # None values are dropped by manim-voiceover's cache serializer; omit them so keys match.
        text = " ".join(text.split())
        key = {"input_text": remove_bookmarks(text), "service": self.engine,
               **{k: v for k, v in self.params.items() if v is not None}}
        # Audio depends on the spoken form: when the current rules read a line differently from
        # the rules its old audio was made with, key on that too (unchanged lines keep their cache).
        spoken = " ".join(spoken_text(text).split())
        if spoken != " ".join(_legacy_spoken_text(text).split()):
            key["spoken"] = spoken
        return key

    def lookup(self, text: str, cache_dir=None) -> dict | None:
        """Cached entry for `text`, or None (no synthesis, no writes)."""
        return self.get_cached_result(self.cache_input_data(text), cache_dir or self.cache_dir)

    def get_cached_result(self, input_data, cache_dir):
        json_path = Path(cache_dir) / DEFAULT_VOICEOVER_CACHE_JSON_FILENAME
        try:
            st = json_path.stat()
        except FileNotFoundError:
            return None
        memo = getattr(self, "_cache_memo", None)
        stamp = (str(json_path), st.st_mtime_ns, st.st_size)
        if memo is None or memo[0] != stamp:
            index = {}
            for entry in load_voiceover_cache(json_path):
                if entry.input_data is None:
                    continue
                k = json.dumps(_match_key(serialize_voiceover_input_data(entry.input_data)), sort_keys=True)
                index.setdefault(k, serialize_voiceover_cache_entry(entry))
            memo = self._cache_memo = (stamp, index)
        hit = memo[1].get(json.dumps(_match_key(dict(input_data)), sort_keys=True))
        if hit is None or not (Path(cache_dir) / hit.get("final_audio", hit.get("original_audio", ""))).is_file():
            return None  # missing audio: re-synthesize rather than crash later
        return dict(hit)

    def _append_cache(self, entry: dict) -> None:
        """Append to cache.json under an exclusive lock with an atomic replace, so
        concurrent renders sharing one cache can neither lose entries nor read a torn file."""
        json_path = Path(self.cache_dir) / DEFAULT_VOICEOVER_CACHE_JSON_FILENAME
        with open(json_path.with_name(json_path.name + ".lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(json_path.read_text()) if json_path.exists() else []
            if not isinstance(data, list):
                raise ValueError(f"{json_path}: voiceover cache must be a JSON list")
            data.append(entry)
            _write_json_atomic(json_path, data)

    def _wrap_generate_from_text(self, text, **kwargs):
        if self.global_speed != 1 or self._whisper_model is not None:
            return super()._wrap_generate_from_text(text, **kwargs)
        # Same normalization as manim-voiceover, but cache hits are not re-appended.
        text = " ".join(text.split())
        path = kwargs.pop("path", None)
        data = self.generate_from_text(text, cache_dir=None, path=path, **kwargs)
        hit = data.pop("_cache_hit", False)
        entry = serialize_voiceover_cache_entry(parse_voiceover_cache_entry(data))
        entry.setdefault("final_audio", entry["original_audio"])
        if not hit:
            self._append_cache(entry)
        return entry

    def generate_from_text(self, text, cache_dir=None, path=None, **kwargs):
        cache_dir = Path(cache_dir or self.cache_dir)
        input_text = remove_bookmarks(text)
        input_data = self.cache_input_data(text)
        cached = self.get_cached_result(input_data, cache_dir)
        if cached is not None:
            # Audio is keyed on spoken text, but bookmarks belong to this render.
            # Reusing old markup loses new timing marks (or retains removed ones).
            return {**cached, "input_text": text, "_cache_hit": True}

        if os.environ.get("STUDIO_TTS_CACHED_ONLY"):
            raise RuntimeError(f"--cached-only: no cached {self.engine} narration for {caption_text(text)[:80]!r} "
                               "(run `study narrate` first)")
        audio_path = str(path) if path else self.get_audio_basename(input_data) + ".wav"
        self._synthesize(text, cache_dir / audio_path)
        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
            "word_boundaries": approx_word_boundaries(input_text, cache_dir / audio_path),
        }

    def _synthesize(self, text: str, out_wav: Path) -> None:
        raise NotImplementedError


class SayService(_LocalService):
    """macOS `say` (offline, free, instant)."""

    engine = "say"

    def __init__(self, voice: str | None = None, rate: int | None = None, **kwargs):
        initialize_speech_service(self, kwargs)
        self.params = {"voice": voice or DEFAULT_VOICE, "rate": int(rate or DEFAULT_RATE)}

    def _synthesize(self, text, out_wav):
        synthesize(text, out_wav, self.params["voice"], self.params["rate"])


# --- Fish Audio S2 Pro (mlx-audio) ---------------------------------------------------
_FISH = {}  # model id -> loaded model (one load per process)


def fish_model_path(model: str = FISH_MODEL) -> Path | None:
    """Snapshot dir of `model` in the local HF cache, or None (never downloads)."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        from huggingface_hub import snapshot_download
        return Path(snapshot_download(model, local_files_only=True))
    except Exception:
        return None


def load_fish(model: str = FISH_MODEL):
    if model in _FISH:
        return _FISH[model]
    path = fish_model_path(model)
    if path is None:
        raise RuntimeError(f"{model} is not in the Hugging Face cache; download it explicitly first "
                           f"(`hf download {model}`, ~7 GB) or use engine say.")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")  # benign model-type notice
    try:
        from mlx_audio.tts.models.fish_qwen3_omni import fish_speech
        from mlx_audio.tts.utils import load_model
    except ImportError as e:
        raise RuntimeError("mlx-audio missing: run `study setup --fish`.") from e
    # Checkpoints converted with mlx-audio 0.4 also quantize embeddings / fast layers,
    # which newer predicates skip. Let the checkpoint decide (quantize layers that ship scales).
    fish_speech.Model.model_quant_predicate = staticmethod(lambda p, m: True)
    t0 = time.time()
    _FISH[model] = load_model(str(path))
    print(f"[fish] loaded {model} in {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
    return _FISH[model]


def _write_pcm16(path: Path, audio, sample_rate: int) -> None:
    import numpy as np

    pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())


def fish_synthesize(text: str, out_wav: Path, model: str = FISH_MODEL, speed: float = 1.0,
                    temperature: float = 0.7, top_p: float = 0.7, seed: int = 0,
                    ref_audio: str | None = None, ref_text: str | None = None,
                    instruct: str | None = None) -> Path:
    """Render `text` with Fish S2 Pro. "[[slnc N]]" -> N ms of exact silence."""
    import mlx.core as mx
    import numpy as np

    m = load_fish(model)
    sr = m.sample_rate
    ref = None
    if ref_audio:
        from mlx_audio.utils import load_audio
        ref = load_audio(ref_audio, sample_rate=sr)

    pieces, t0 = [], time.time()
    parts = _SLNC.split(spoken_text(text))  # [text, ms, text, ms, ...]
    for i, part in enumerate(parts):
        if i % 2:
            pieces.append(np.zeros(int(sr * int(part) / 1000), dtype=np.float32))
            continue
        part = " ".join(_SAY_CMD.sub("", part).split())
        if not part:
            continue
        mx.random.seed(seed)
        # every [[slnc]]-separated part is a separate generate() call: same ref + seed for each
        for r in m.generate(text=part, ref_audio=ref, ref_text=ref_text, instruct=instruct,
                            temperature=temperature, top_p=top_p, max_tokens=FISH_MAX_TOKENS,
                            verbose=False):
            pieces.append(np.asarray(r.audio, dtype=np.float32))
    audio = np.concatenate(pieces) if pieces else np.zeros(int(sr * 0.2), dtype=np.float32)
    dur = len(audio) / sr
    print(f"[fish] {dur:.1f}s audio in {time.time() - t0:.1f}s: {caption_text(text)[:60]!r}",
          file=sys.stderr, flush=True)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        _write_pcm16(raw, audio, sr)
        _to_wav(raw, out_wav, tempo=speed)  # pitch-preserving speed change
    return out_wav


class FishService(_LocalService):
    """Fish Audio S2 Pro via mlx-audio: high quality, local, voice cloning."""

    engine = "fish"

    def __init__(self, model: str = FISH_MODEL, speed: float = 1.0, temperature: float = 0.7,
                 top_p: float = 0.7, seed: int = 0, ref_audio: str | None = None,
                 ref_text: str | None = None, instruct: str | None = None, **kwargs):
        initialize_speech_service(self, kwargs)
        if ref_audio and not ref_text:
            raise ValueError("fish voice cloning needs `ref_text` (the exact words spoken in ref_audio)")
        if ref_audio and not Path(ref_audio).is_file():
            raise FileNotFoundError(f"ref_audio not found: {ref_audio}")
        self.ref_audio = ref_audio  # not in the cache key: its path may move (keyed by ref_sha1)
        self.params = {"model": model, "speed": float(speed), "temperature": float(temperature),
                       "top_p": float(top_p), "seed": int(seed),
                       "ref_text": ref_text, "instruct": instruct,
                       # content hash so re-recording the clip invalidates the cache
                       "ref_sha1": hashlib.sha1(Path(ref_audio).read_bytes()).hexdigest() if ref_audio else None}

    def preload(self) -> float:
        t0 = time.time()
        load_fish(self.params["model"])
        return time.time() - t0

    def _synthesize(self, text, out_wav):
        p = {k: v for k, v in self.params.items() if k != "ref_sha1"}
        fish_synthesize(text, out_wav, ref_audio=self.ref_audio, **p)


# --- LiquidAI LFM3-Audio-2B (transformers, MPS) --------------------------------------
LFM3_MODEL = "LiquidAI/LFM3-Audio-2B"
LFM3_REVISION = "9d49701c372d6011d900f6abb40c6b296fb706dd"  # remote code: never float
LFM3_LOCALES = {"en-US": "American English", "en-GB": "British English", "en-UK": "British English"}
LFM3_SAMPLING = {"audio_temperature": 1.0, "audio_top_k": 128, "audio_repetition_penalty": 1.1,
                 "audio_repetition_window": 4096}
LFM3_MAX_TOKENS = 2048
_LFM3 = {}  # (model, revision) -> (model, processor, codec, device)


def lfm3_model_path(model: str = LFM3_MODEL, revision: str = LFM3_REVISION) -> Path | None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        from huggingface_hub import snapshot_download
        return Path(snapshot_download(model, revision=revision, local_files_only=True))
    except Exception:
        return None


def load_lfm3(model: str = LFM3_MODEL, revision: str = LFM3_REVISION):
    key = (model, revision)
    if key in _LFM3:
        return _LFM3[key]
    path = lfm3_model_path(model, revision)
    if path is None:
        raise RuntimeError(f"{model}@{revision[:8]} is not in the Hugging Face cache; download it explicitly "
                           f"(`hf download {model} --revision {revision}`, ~4.2 GB) or use engine say.")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    try:
        import torch
        from transformers.utils import logging as hf_logging
        hf_logging.disable_progress_bar()
        from transformers import AutoModelForMultimodalLM, AutoProcessor
    except ImportError as e:
        raise RuntimeError("torch/transformers missing: run `study setup --lfm3`.") from e
    import warnings
    warnings.filterwarnings("ignore", message=".*causal_conv1d.*")  # CUDA kernel -> torch fallback
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    # MPS does the model work; excess CPU threads contend with the desktop and
    # other section workers. Preserve an explicitly smaller existing budget.
    if dev == "mps" and torch.get_num_threads() > 2:
        torch.set_num_threads(2)
    t0 = time.time()
    m = AutoModelForMultimodalLM.from_pretrained(str(path), dtype=torch.bfloat16, device_map=dev,
                                                 trust_remote_code=True).eval()
    proc = AutoProcessor.from_pretrained(str(path), trust_remote_code=True)
    codec = proc.audio_tokenizer.to(device=dev).eval()
    _LFM3[key] = (m, proc, codec, dev)
    print(f"[lfm3] loaded {model}@{revision[:8]} on {dev} in {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
    return _LFM3[key]


def lfm3_parts(text: str, pause_ms: int) -> list:
    """Spoken text -> [str | int(ms silence), ...]: "[[slnc N]]" is exact, Fish tags like
    "[pause]" (which LFM3 would read aloud) become `pause_ms` of silence."""
    out = []
    for i, chunk in enumerate(_SLNC.split(spoken_text(text))):
        if i % 2:
            out.append(int(chunk))
            continue
        for j, sub in enumerate(_TAG.split(_SAY_CMD.sub("", chunk))):
            if j:
                out.append(int(pause_ms))
            sub = " ".join(sub.split())
            if sub and re.search(r"\w", sub):
                out.append(sub)
    merged = []
    for x in out:  # merge adjacent silences; drop leading/trailing ones (clip edges stay natural)
        if isinstance(x, int) and merged and isinstance(merged[-1], int):
            merged[-1] += x
        else:
            merged.append(x)
    while merged and isinstance(merged[0], int):
        merged.pop(0)
    while merged and isinstance(merged[-1], int):
        merged.pop()
    return merged


def loudness_normalize(src: Path, out_wav: Path, lufs: float = -18.0, true_peak: float = -1.5,
                       tempo: float = 1.0) -> None:
    """Two-pass EBU R128 loudnorm (linear gain when the true-peak limit allows) -> 44.1 kHz mono."""
    pre = [f"atempo={tempo:.4f}"] if abs(tempo - 1.0) > 1e-3 else []
    target = f"I={lufs}:TP={true_peak}:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af",
                        ",".join(pre + [f"loudnorm={target}:print_format=json"]), "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    if m["input_i"] in ("-inf", "inf"):  # silent clip: nothing to normalize
        _to_wav(src, out_wav, tempo)
        return
    meas = (f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
            f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                    ",".join(pre + [f"loudnorm={target}:{meas}"]), "-ar", "44100", "-ac", "1", str(out_wav)],
                   check=True)


def lfm3_synthesize(text: str, out_wav: Path, locale: str = "en-US", gender: str = "female", seed: int = 0,
                    speed: float = 1.0, pause_ms: int = 350, lufs: float = -18.0, true_peak: float = -1.5,
                    model: str = LFM3_MODEL, revision: str = LFM3_REVISION, **_ignored) -> Path:
    import numpy as np
    import torch

    m, proc, codec, dev = load_lfm3(model, revision)
    system = f"Perform TTS in {LFM3_LOCALES.get(locale, locale)} using a {gender} voice."
    sr = 24_000
    pieces, t0 = [], time.time()
    for part in lfm3_parts(text, pause_ms) or [200]:
        if isinstance(part, int):
            pieces.append(np.zeros(int(sr * part / 1000), dtype=np.float32))
            continue
        torch.manual_seed(seed)  # same seed for every part: keeps the (seed-dependent) speaker
        conv = [{"role": "system", "content": system}, {"role": "user", "content": part},
                {"role": "assistant", "content": "<|audio_start|>"}]
        inputs = proc.apply_chat_template(conv, continue_final_message=True, tokenize=True,
                                          return_dict=True, return_tensors="pt").to(dev)
        with torch.inference_mode():
            out = m.generate(**inputs, max_new_tokens=LFM3_MAX_TOKENS, return_dict_in_generate=True,
                             **LFM3_SAMPLING)
            n = int(out.audio_lengths[0])
            wav = codec.decode(out.audio_codes[:1, :, :n]).audio_values[0]
        pieces.append(wav.float().cpu().numpy().reshape(-1))
    # Keep the allocator warm across lines/lessons. empty_cache() here forces
    # repeated MPS allocations; model lifetime (one narrate process) bounds memory.
    audio = np.concatenate(pieces)
    print(f"[lfm3] {len(audio) / sr:.1f}s audio in {time.time() - t0:.1f}s: {caption_text(text)[:60]!r}",
          file=sys.stderr, flush=True)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        _write_pcm16(raw, audio, sr)
        loudness_normalize(raw, out_wav, lufs, true_peak, tempo=speed)
    return out_wav


class LFM3Service(_LocalService):
    """LiquidAI LFM3-Audio-2B: fast local TTS, 4 English voices (US/UK x female/male), no cloning."""

    engine = "lfm3"

    def __init__(self, locale: str = "en-US", gender: str = "female", seed: int = 0, speed: float = 1.0,
                 pause_ms: int = 350, lufs: float = -18.0, true_peak: float = -1.5,
                 model: str = LFM3_MODEL, revision: str = LFM3_REVISION, **kwargs):
        for k in ("name", "preset", "stats", "description"):
            kwargs.pop(k, None)
        initialize_speech_service(self, kwargs)
        if gender not in ("female", "male"):
            raise ValueError(f"lfm3 gender must be female or male, not {gender!r}")
        self.params = {"model": model, "revision": revision, "locale": locale, "gender": gender,
                       "seed": int(seed), "speed": float(speed), "pause_ms": int(pause_ms),
                       "lufs": float(lufs), "true_peak": float(true_peak), **LFM3_SAMPLING}

    def preload(self) -> float:
        t0 = time.time()
        load_lfm3(self.params["model"], self.params["revision"])
        return time.time() - t0

    def _synthesize(self, text, out_wav):
        lfm3_synthesize(text, out_wav, **self.params)


# --- selection --------------------------------------------------------------------
ENGINES = {"say": SayService, "fish": FishService, "lfm3": LFM3Service}


def voice_config(spec: dict, lesson_dir: Path | None = None, engine: str | None = None) -> dict:
    """Normalize lesson.yaml `voice:` / `rate:` into {"engine": ..., **params}.
    Relative `ref_audio` paths are resolved against the lesson dir."""
    v = spec.get("voice")
    cfg = dict(v) if isinstance(v, dict) else {"engine": "say", "name": v or DEFAULT_VOICE}
    cfg.setdefault("engine", "say")
    if engine and engine != cfg["engine"]:
        # --engine override: the lesson's presets/params belong to its own engine (an lfm3
        # preset is not a fish clip and vice versa), so fall back to the new engine's defaults.
        cfg = {"engine": engine, **({"speed": cfg["speed"]} if "speed" in cfg else {})}
    if cfg["engine"] == "say":
        name = cfg.get("name") or (v if isinstance(v, str) else None) or DEFAULT_VOICE
        cfg = {"engine": "say", "voice": name, "rate": int(cfg.get("rate") or spec.get("rate") or DEFAULT_RATE)}
    elif cfg["engine"] not in ENGINES:
        raise ValueError(f"unknown voice engine {cfg['engine']!r} (choose from {', '.join(ENGINES)})")
    if cfg.get("ref_audio") and lesson_dir is not None:
        cfg["ref_audio"] = str((lesson_dir / os.path.expanduser(cfg["ref_audio"])).resolve())
    if cfg["engine"] == "lfm3":
        preset = cfg.pop("preset", None)
        if preset or not (cfg.get("locale") or cfg.get("gender")):
            from studio import voices
            cfg = {**voices.lfm3_preset(preset or DEFAULT_LFM3_PRESET), **cfg}
        cfg.pop("name", None)
    if cfg["engine"] == "fish":
        preset = cfg.pop("preset", None)
        if not cfg.get("ref_audio") and preset != "none":  # `preset: none` = new random voice per line
            from studio import voices
            cfg.update(voices.preset_ref(preset or voices.DEFAULT_PRESET))
        if cfg.get("instruct") and not cfg.get("ref_audio"):
            print("[voice] warning: fish `instruct` without a reference clip is often read aloud",
                  file=sys.stderr)
    if isinstance(spec.get("pronounce"), dict) and spec["pronounce"]:
        cfg["pronounce"] = {str(k): str(v) for k, v in spec["pronounce"].items()}
    return cfg


def make_service(cfg: dict | None = None) -> SpeechService:
    """Speech service from a voice_config() dict (default: $STUDIO_TTS, else `say`)."""
    if cfg is None:
        cfg = json.loads(os.environ.get("STUDIO_TTS") or "{}") or {"engine": "say"}
    cfg = dict(cfg)
    LESSON_PRONOUNCE.clear()
    LESSON_PRONOUNCE.update({str(k): str(v) for k, v in (cfg.pop("pronounce", None) or {}).items()})
    engine = cfg.pop("engine", "say")
    if engine in ("fish", "lfm3"):
        cfg.pop("name", None)
    return ENGINES[engine](**cfg)


def engine_status() -> dict[str, str]:
    """{engine: "ok ..." | "missing: reason"} without loading any model."""
    import importlib.util

    say = "ok" if shutil.which("say") else "missing: macOS `say` not found"
    if importlib.util.find_spec("mlx_audio") is None:
        fish = "missing: run `study setup --fish` (Apple Silicon only)"
    elif fish_model_path() is None:
        fish = f"missing: {FISH_MODEL} not in HF cache (`hf download {FISH_MODEL}`, ~7 GB)"
    else:
        fish = f"ok ({FISH_MODEL}, cached)"
    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("transformers") is None:
        lfm3 = "missing: run `study setup --lfm3`"
    elif lfm3_model_path() is None:
        lfm3 = f"missing: {LFM3_MODEL}@{LFM3_REVISION[:8]} not in HF cache (`hf download {LFM3_MODEL}`, ~4.2 GB)"
    else:
        lfm3 = f"ok ({LFM3_MODEL}@{LFM3_REVISION[:8]}, cached)"
    return {"say": say, "fish": fish, "lfm3": lfm3}
