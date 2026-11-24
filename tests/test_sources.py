"""`study sources`: timed sources.md from notes.md source map + script.md + final captions.srt."""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from studio import sources

SCRIPT = textwrap.dedent("""\
    # Ports

    ## Ports
    [01] A port number picks the process [pause] on a host.
    beats: show the port box
      and the host
    [02] There are 65,535 of them.

    [03] Well known ports sit below 1024.

    ## Udp
    [01] UDP adds almost nothing.
    [02] It keeps a checksum <bookmark mark='c'/>for the payload.
    """)

# Captions spell numbers differently and split words across cues, as real ones do.
SRT = textwrap.dedent("""\
    1
    00:00:00,000 --> 00:00:02,000
    A port number picks the process

    2
    00:00:02,500 --> 00:00:03,500
    on a host.

    3
    00:00:04,000 --> 00:00:06,000
    There are 65535 of them.

    4
    00:00:06,500 --> 00:00:09,000
    Well known ports sit below 1,024.

    5
    00:00:10,000 --> 00:00:12,000
    UDP adds almost nothing.

    6
    00:00:12,500 --> 00:00:15,250
    It keeps a checksum for the payload.
    """)

NOTES = textwrap.dedent("""\
    # Notes

    ## Coverage and source map
    | Slide | Scene [blocks] | Locator | Displayed label | Provenance | Actual times |
    |---|---|---|---|---|---|
    | 10 | Ports [01]–[02] | bullets 1–2 | Deck · slide 10 | source | TODO |
    | 10 | Ports [03] | — | Added explanation | added | TODO |
    | 12 | Udp (all) | slide-012.png | Deck · slide 12 | source | TODO |

    ## Added explanations / corrections / external references
    - RFC 6335 §6: port ranges.

    External: https://www.rfc-editor.org/rfc/rfc768
    """)

LESSON = textwrap.dedent("""\
    title: Ports
    credits:
      - "Deck: `deck.pptx`, Example Course, A. Author."
      - "Numbering: original deck slide numbers."
    scenes:
      - {name: Ports}
      - {name: Udp}
    """)


def make_section(root: Path, notes=NOTES, srt=SRT, lesson=LESSON, script=SCRIPT) -> Path:
    s = root / "sections" / "01-ports"
    (s / "build").mkdir(parents=True)
    (s / "script.md").write_text(script)
    (s / "notes.md").write_text(notes)
    (s / "lesson.yaml").write_text(lesson)
    (s / "build" / "captions.srt").write_text(srt)
    return s


class AlignTests(unittest.TestCase):
    def test_blocks_align_through_number_formats_and_markup(self):
        blocks = sources.parse_script(SCRIPT)
        self.assertEqual([(b.scene, b.n) for b in blocks],
                         [("Ports", 1), ("Ports", 2), ("Ports", 3), ("Udp", 1), ("Udp", 2)])
        self.assertNotIn("beats", blocks[0].text)
        times = sources.align(blocks, sources.parse_srt(SRT))
        self.assertEqual(times[("Ports", 1)], (0.0, 3.5))
        self.assertEqual(times[("Ports", 2)], (4.0, 6.0))
        self.assertEqual(times[("Ports", 3)], (6.5, 9.0))
        self.assertEqual(times[("Udp", 2)], (12.5, 15.25))

    def test_unrelated_captions_raise_instead_of_guessing(self):
        blocks = sources.parse_script(SCRIPT)
        bad = "1\n00:00:00,000 --> 00:00:02,000\nCompletely different words here.\n"
        with self.assertRaises(sources.SourcesError):
            sources.align(blocks, sources.parse_srt(bad))

    def test_beat_cells_expand_ranges_lists_and_all(self):
        known = {("Ports", n) for n in (1, 2, 3, 4, 5)}
        self.assertEqual(sources.beat_blocks("Ports [01]–[03], [05]", known),
                         [("Ports", 1), ("Ports", 2), ("Ports", 3), ("Ports", 5)])
        self.assertEqual(sources.beat_blocks("Ports [02]-[03]", known), [("Ports", 2), ("Ports", 3)])
        self.assertEqual(len(sources.beat_blocks("Ports (all)", known)), 5)
        self.assertEqual(sources.beat_blocks("Ports · blocks [04]", known), [("Ports", 4)])
        self.assertEqual(sources.beat_blocks("Nowhere [01]", known), [])


class SectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_section_map_is_timed_and_written(self):
        s = make_section(self.root)
        result = sources.section_sources(s)
        self.assertEqual(result["untimed"], [])
        text = (s / "build" / "sources.md").read_text()
        self.assertIn("Deck: `deck.pptx`, Example Course, A. Author.", text)
        self.assertIn("| Ports [01]–[02] | slide 10 (bullets 1–2) | Deck · slide 10 | source | 0:00.00–0:06.00 |", text)
        self.assertIn("| Ports [03] | slide 10 | Added explanation | added | 0:06.50–0:09.00 |", text)
        self.assertIn("| Udp (all) | slide 12 (slide-012.png) | Deck · slide 12 | source | 0:10.00–0:15.25 |", text)
        self.assertIn("RFC 6335 §6", text)
        self.assertIn("External: https://www.rfc-editor.org/rfc/rfc768", text)
        data = json.loads((s / "build" / "sources.json").read_text())
        self.assertEqual(data["rows"][0]["start"], 0.0)
        self.assertEqual(data["rows"][2]["end"], 15.25)

    def test_tables_without_a_slide_column_keep_their_locator(self):
        notes = NOTES.replace("| Slide | Scene [blocks] | Locator |", "| beat | original locator |") \
            .replace("|---|---|---|---|---|---|", "|---|---|---|---|---|")
        notes = "\n".join(l.replace("| 10 | ", "| ").replace("| 12 | ", "| ") for l in notes.splitlines())
        s = make_section(self.root, notes=notes)
        sources.section_sources(s)
        self.assertIn("| Ports [01]–[02] | bullets 1–2 | Deck · slide 10 |", (s / "build" / "sources.md").read_text())

    def test_untimed_rows_fail_and_write_nothing(self):
        notes = NOTES.replace("| 12 | Udp (all)", "| 12 | Missing [01]")
        s = make_section(self.root, notes=notes)
        with self.assertRaises(sources.SourcesError) as e:
            sources.section_sources(s)
        self.assertIn("Missing [01]", str(e.exception))
        self.assertFalse((s / "build" / "sources.md").exists())

    def test_header_must_be_real_not_todo(self):
        s = make_section(self.root, lesson=LESSON.replace("A. Author.", "TODO"))
        with self.assertRaises(sources.SourcesError):
            sources.section_sources(s)

    def test_header_falls_back_to_collection_yaml(self):
        lesson = "title: Ports\nsources: [source/slides.md]\nscenes:\n  - {name: Ports}\n  - {name: Udp}\n"
        s = make_section(self.root, lesson=lesson)
        (self.root / "collection.yaml").write_text(
            "title: Course\ncredits:\n  - 'Deck: shared credit line.'\nsections:\n"
            "- {id: 01-ports, title: Ports, path: sections/01-ports}\n")
        sources.section_sources(s)
        self.assertIn("Deck: shared credit line.", (s / "build" / "sources.md").read_text())

    def test_missing_source_map_is_an_error(self):
        s = make_section(self.root, notes="# Notes\n\nNo table.\n")
        with self.assertRaises(sources.SourcesError):
            sources.section_sources(s)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class CombinedTests(unittest.TestCase):
    def test_combined_map_shifts_by_measured_chapter_starts(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            root = Path(tmp)
            make_section(root)
            second = root / "sections" / "02-more"
            shutil.copytree(root / "sections" / "01-ports", second)
            (root / "collection.yaml").write_text(
                "title: Course\ncredits:\n  - 'Deck: shared.'\nsections:\n"
                "- {id: 01-ports, title: Ports, path: sections/01-ports}\n"
                "- {id: 02-more, title: More ports, path: sections/02-more}\n")
            video = root / "combined" / "build" / "combined.mp4"
            video.parent.mkdir(parents=True)
            meta = root / "meta.txt"
            meta.write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=16500\ntitle=Ports\n"
                            "[CHAPTER]\nTIMEBASE=1/1000\nSTART=16500\nEND=33000\ntitle=More ports\n")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x36:d=33",
                            "-i", str(meta), "-map_metadata", "1", "-c:v", "libx264", str(video)], check=True)
            result = sources.combined_sources(root)
            text = (root / "combined" / "build" / "sources.md").read_text()
            self.assertEqual(result["rows"], 6)
            self.assertIn("## Ports (01-ports) — starts 0:00:00.00", text)
            self.assertIn("## More ports (02-more) — starts 0:00:16.50", text)
            self.assertIn("| Udp (all) | slide 12 (slide-012.png) | Deck · slide 12 | source | 0:00:26.50–0:00:31.75 |", text)
            self.assertIn("Deck: shared.", text)

    def test_chapter_count_must_match_sections(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            root = Path(tmp)
            make_section(root)
            (root / "collection.yaml").write_text(
                "title: C\ncredits: ['x']\nsections:\n- {id: 01-ports, title: P, path: sections/01-ports}\n"
                "- {id: 02-gone, title: G, path: sections/02-gone}\n")
            video = root / "combined" / "build" / "combined.mp4"
            video.parent.mkdir(parents=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x36:d=2",
                            "-c:v", "libx264", str(video)], check=True)
            with self.assertRaises(sources.SourcesError):
                sources.combined_sources(root)


class CliTests(unittest.TestCase):
    def test_cli_reports_and_exits_nonzero_on_failure(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            root = Path(tmp)
            good = make_section(root)
            self.assertEqual(sources.main([str(good)]), 0)
            bad = root / "sections" / "02-bad"
            shutil.copytree(good, bad)
            (bad / "notes.md").write_text(NOTES.replace("Udp (all)", "Nope [01]"))
            self.assertEqual(sources.main([str(good), str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
