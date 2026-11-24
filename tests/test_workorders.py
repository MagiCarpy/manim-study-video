"""Scene work orders (strategy D): compact per-scene bundles + a sequential headless runner."""
import json
import os
import shlex
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from studio import workorders as wo

SCRIPT = textwrap.dedent("""\
    # Script — 05 Teardown

    Frozen by the planner. Colours follow brief.md.

    ## WhyClose
    [01] Our connection is open. [pause] How do we end it?
    beats: hosts BLUE/TEAL with ESTABLISHED. Label Deck · slide 35.

    [02] A peer can crash without a word.
    beats: server dims. Label Deck · slide 35.

    ## FinHandshake
    [01] The server sends a FIN.
    beats: Trace A step 1; FIN arrow GOLD. Label Deck · slide 36.

    ## TimeWait
    [01] The active closer waits.
    beats: TIME_WAIT pill. Label Deck · slide 37.
    """)

NOTES = textwrap.dedent("""\
    # Notes

    ## Learning goals
    Long general text that no scene needs verbatim.

    ## Vocabulary — where defined
    | term | scene | on screen |
    |---|---|---|
    | FIN | FinHandshake [01] | GOLD arrow label |
    | MSL | TimeWait [01] | bar label |
    Animator note: show a one-line gloss under each state label when it first appears.

    ## Worked example and verified event sequences
    ### Trace A — normal close (FinHandshake [01]); slide 36
    server FIN seq 8001 -> browser; ack 8002.
    ### Trace B — lost final ACK (TimeWait [01]); slide 37
    final ACK lost; FIN retransmitted.

    ## Source map
    | Slide | Scene [blocks] | Locator | Displayed label | Provenance | Actual times |
    |---|---|---|---|---|---|
    | 35 | WhyClose [01]–[02] | bullets | Deck · slide 35 | source | TODO |
    | 36 | FinHandshake (all) | figure | Deck · slide 36 | source | TODO |
    | 37 | TimeWait [01] | — | Deck · slide 37 | source | TODO |

    ## Teaching storyboard and transitions
    WhyClose ends on the disconnect arrow; FinHandshake opens on the same two lifelines.

    ## Slide excerpts
    ### Slide 35 [slide 35]
    So now how do we disconnect
    ### Slide 36 [slide 36]
    FIN handshake figure
    ### Slide 37 [slide 37]
    TIME_WAIT figure
    """)

BRIEF = textwrap.dedent("""\
    # Collection brief

    ## Sections
    01 … 07 table nobody needs here.

    ## Notation and colours (all sections)
    Client BLUE left, server TEAL right; FIN GOLD; ACK GREEN.

    ## Citation convention
    `Deck · slide N`.

    ## Known slide issues (fix in speech and visuals; label as stated)
    | Slide | Issue |
    |---|---|
    | 12 | field order |
    | 36 | server drawn on the left |

    ## Rendering & resource rules
    Locks and queue details the worker order already carries.
    """)

LESSON = {"title": "Teardown", "voice": {"engine": "lfm3", "preset": "p"},
          "scenes": [{"name": "WhyClose"}, {"name": "FinHandshake"}, {"name": "TimeWait"}]}

SCENES_HEADER = textwrap.dedent("""\
    from manim import FadeIn
    from studio import style
    from studio.base import StudyScene
    from studio.cslib import Timeline, host

    LEFT_X, RIGHT_X = -4.5, 4.5
    CLIENT = style.BLUE


    def local_helper():
        return 1


    class WhyClose(StudyScene):
        def construct(self):
            self.wait(1)
    """)


def make_section(root: Path, scenes_py: str | None = None) -> Path:
    (root / "brief.md").write_text(BRIEF)
    s = root / "sections" / "05-teardown"
    s.mkdir(parents=True)
    (s / "script.md").write_text(SCRIPT)
    (s / "notes.md").write_text(NOTES)
    (s / "lesson.yaml").write_text(yaml.safe_dump(LESSON))
    (s / "checkpoint.yaml").write_text(yaml.safe_dump({"section_id": "05-teardown", "state": "frozen"}))
    if scenes_py is not None:
        (s / "scenes.py").write_text(scenes_py)
    return s


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_order_contains_only_its_scene_and_relevant_context(self):
        s = make_section(self.root)
        text = wo.render_order(s, ["FinHandshake"], index=2, total=3)
        self.assertIn("[01] The server sends a FIN.", text)          # its script, verbatim
        self.assertIn("Trace A step 1", text)                        # its beats
        self.assertNotIn("A peer can crash", text)                   # not other scenes' script
        self.assertNotIn("The active closer waits", text)
        self.assertIn("server FIN seq 8001", text)                   # its trace
        self.assertNotIn("FIN retransmitted", text)                  # not another scene's trace
        self.assertIn("| 36 | FinHandshake (all) |", text)           # its source-map rows
        self.assertIn("FIN handshake figure", text)                  # its slide excerpt
        self.assertNotIn("TIME_WAIT figure", text)
        self.assertIn("FIN GOLD", text)                              # brief notation
        self.assertIn("| 36 | server drawn on the left |", text)     # known issue for its slide
        self.assertNotIn("| 12 | field order |", text)
        self.assertNotIn("Locks and queue details", text)            # irrelevant brief sections
        self.assertNotIn("Long general text", text)                  # irrelevant notes sections
        self.assertIn("FinHandshake opens on the same two lifelines", text)  # transitions

    def test_order_keeps_lines_naming_the_scene_and_animator_notes_from_any_section(self):
        s = make_section(self.root)
        text = wo.render_order(s, ["FinHandshake"], index=2, total=3)
        self.assertIn("| FIN | FinHandshake [01] | GOLD arrow label |", text)
        self.assertIn("| term | scene | on screen |", text)               # table header kept
        self.assertNotIn("| MSL | TimeWait [01] |", text)
        self.assertIn("Animator note: show a one-line gloss", text)

    def test_rules_say_concept_first_still_needs_a_beat_per_idea(self):
        s = make_section(self.root)
        text = wo.render_order(s, ["FinHandshake"], index=2, total=3)
        self.assertIn("not fewer beats", text)
        self.assertIn("--hold", text)

    def test_order_carries_existing_scenes_py_header_not_its_bodies(self):
        s = make_section(self.root, SCENES_HEADER)
        text = wo.render_order(s, ["FinHandshake"], index=2, total=3)
        self.assertIn("LEFT_X, RIGHT_X = -4.5, 4.5", text)
        self.assertIn("from studio.cslib import Timeline, host", text)
        self.assertIn("local_helper", text)                          # named so it is reused
        self.assertNotIn("return 1", text)                           # but not its body
        self.assertIn("WhyClose", text)                              # existing scene listed

    def test_order_states_rules_budget_and_commands(self):
        s = make_section(self.root)
        text = wo.render_order(s, ["WhyClose"], index=1, total=3, call_budget=25)
        for must in ("--scene WhyClose", "--engine say", "patch", "# concept:", "25", "api cslib --grep",
                     "first work order", 'checkpoint "$S" --scene WhyClose --say-draft built --layout', "python -c"):
            self.assertIn(must, text)
        self.assertNotIn("write to a temp file", text)       # no hand-edited YAML

    def test_worker_draft_uses_one_combined_review_command(self):
        section = make_section(self.root)
        for brief in (wo.render_order(section, ['WhyClose'], 1, 3), wo.render_consistency(section)):
            self.assertIn('review "$S" --lint --layout --sheet', brief)
            self.assertNotIn('"$STUDY" build', brief)

    def test_bundle_is_small(self):
        s = make_section(self.root)
        self.assertLess(len(wo.render_order(s, ["FinHandshake"], index=2, total=3)), 12_000)

    def test_plan_groups_scenes_and_ends_with_consistency_pass(self):
        s = make_section(self.root)
        plan = wo.plan(s, groups=[["FinHandshake", "TimeWait"]])
        self.assertEqual([o["scenes"] for o in plan], [["WhyClose"], ["FinHandshake", "TimeWait"], []])
        self.assertEqual(plan[-1]["kind"], "consistency")
        with self.assertRaises(ValueError):
            wo.plan(s, groups=[["Nope"]])

    def test_long_sections_pair_scenes_by_default(self):
        s = make_section(self.root)
        names = [f"S{i}" for i in range(1, 9)]
        (s / "lesson.yaml").write_text(yaml.safe_dump(dict(LESSON, scenes=[{"name": n} for n in names])))
        self.assertEqual([o["scenes"] for o in wo.plan(s)][:-1],
                         [["S1", "S2"], ["S3", "S4"], ["S5", "S6"], ["S7", "S8"]])
        (s / "lesson.yaml").write_text(yaml.safe_dump(dict(LESSON, scenes=[{"name": n} for n in names[:5]])))
        self.assertEqual([o["scenes"] for o in wo.plan(s)][:-1], [["S1", "S2"], ["S3", "S4"], ["S5"]])
        self.assertEqual([o["scenes"] for o in wo.plan(s, per_order=1)][:-1], [[n] for n in names[:5]])
        (s / "lesson.yaml").write_text(yaml.safe_dump(dict(LESSON, scenes=[{"name": n} for n in names[:4]])))
        self.assertEqual([o["scenes"] for o in wo.plan(s)][:-1], [[n] for n in names[:4]])

    def test_budget_grows_with_scenes_per_order(self):
        self.assertEqual(wo.order_budget(25, 1), 25)
        self.assertEqual(wo.order_budget(25, 2), 35)
        self.assertEqual(wo.order_budget(25, 3), 45)

    def test_explicit_grouping_wins_over_auto_pairing(self):
        s = make_section(self.root)
        scenes = [{"name": f"S{i}"} for i in range(1, 7)]
        scenes[0]["workorder"] = "a"; scenes[1]["workorder"] = "a"; scenes[2]["workorder"] = "a"
        (s / "lesson.yaml").write_text(yaml.safe_dump(dict(LESSON, scenes=scenes)))
        self.assertEqual([o["scenes"] for o in wo.plan(s)][:-1], [["S1", "S2", "S3"], ["S4"], ["S5"], ["S6"]])

    def test_lesson_yaml_workorder_key_groups_scenes(self):
        s = make_section(self.root)
        spec = dict(LESSON, scenes=[{"name": "WhyClose"}, {"name": "FinHandshake", "workorder": "close"},
                                    {"name": "TimeWait", "workorder": "close"}])
        (s / "lesson.yaml").write_text(yaml.safe_dump(spec))
        self.assertEqual([o["scenes"] for o in wo.plan(s)][:2], [["WhyClose"], ["FinHandshake", "TimeWait"]])

    def test_consistency_order_reviews_whole_section(self):
        s = make_section(self.root)
        text = wo.render_consistency(s)
        for must in ("--lint --layout --sheet", 'checkpoint "$S" --draft', "narrate", "--check", "consistency"):
            self.assertIn(must, text)


class CollectionQueueTests(unittest.TestCase):
    def test_changed_frozen_plan_never_dispatches(self):
        from studio.checkpoint import plan_hashes
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp)
            section = make_section(root)
            (root / 'collection.yaml').write_text(yaml.safe_dump({'sections': [{'id': section.name}]}))
            (section / 'checkpoint.yaml').write_text(yaml.safe_dump({
                'state': 'frozen', 'frozen_plan': plan_hashes(section),
            }))
            (section / 'script.md').write_text('changed since freeze')
            result = wo.run_collection(root, lambda _: self.fail('stale plan was dispatched'))
            self.assertEqual(result['status'], 'incomplete')
            self.assertIn('changed', result['incomplete'][section.name]['reason'])

    def test_follow_stops_on_quota_and_resumes_from_the_saved_section(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp)
            section = make_section(root)
            ck = section / 'checkpoint.yaml'
            ck.write_text('state: scaffolded\n')
            (root / 'collection.yaml').write_text(yaml.safe_dump({'sections': [{'id': section.name}]}))
            with patch.object(wo.time, 'sleep', side_effect=lambda _: ck.write_text('state: frozen\n')):
                first = wo.run_collection(root, lambda _: {'status': 'paused', 'reason': 'quota test'}, follow=True)
            self.assertEqual(first['status'], 'paused')
            self.assertEqual(first['section'], section.name)

            def finish(path):
                self.assertEqual(path, section.resolve())
                ck.write_text('state: draft\ncompleted: [draft_review]\n')
                return {'status': 'done'}

            self.assertEqual(wo.run_collection(root, finish)['status'], 'done')
            records = [json.loads(row) for row in (root / 'build/workorders/queue.jsonl').read_text().splitlines()]
            self.assertEqual([r['kind'] for r in records if r['kind'] in ('resume', 'pause')], ['resume', 'pause', 'resume'])

    def test_runs_frozen_independent_sections_as_they_arrive_then_resumes(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp)
            first = make_section(root)
            other = first.with_name('02-scope')
            other.mkdir()
            for name in ('lesson.yaml', 'script.md', 'notes.md'):
                (other / name).write_bytes((first / name).read_bytes())
            (root / 'collection.yaml').write_text(yaml.safe_dump({'sections': [
                {'id': other.name}, {'id': first.name},
            ]}))
            (other / 'checkpoint.yaml').write_text('state: scaffolded\n')
            calls = []

            def animate(section):
                calls.append(section.name)
                ck = yaml.safe_load((section / 'checkpoint.yaml').read_text())
                ck.update(state='draft', completed=['draft_review'])
                (section / 'checkpoint.yaml').write_text(yaml.safe_dump(ck))
                return {'status': 'done'}

            self.assertEqual(wo.run_collection(root, animate)['status'], 'waiting')
            self.assertEqual(calls, [first.name])
            (other / 'checkpoint.yaml').write_text('state: frozen\n')
            self.assertEqual(wo.run_collection(root, animate)['status'], 'done')
            self.assertEqual(calls, [first.name, other.name])


FAKE_HERMES = textwrap.dedent("""\
    import os, re, sys, yaml, pathlib
    args = sys.argv[1:]
    q = pathlib.Path(args[args.index('--query-file') + 1]).read_text()
    log = pathlib.Path(os.environ['FAKE_LOG']); log.write_text(log.read_text() + ' '.join(args) + '\\n' if log.exists() else ' '.join(args) + '\\n')
    sec = pathlib.Path(args[args.index('--in') + 1])
    m = re.search(r'^Scenes: (.*)$', q, re.M)
    scenes = [x.strip() for x in m.group(1).split(',')] if m and m.group(1).strip() else []
    if os.environ.get('FAKE_QUOTA'):
        print('Error: usage limit reached for this 5-hour window'); sys.exit(1)
    ck = sec / 'checkpoint.yaml'; d = yaml.safe_load(ck.read_text()) or {}
    skip = os.environ.get('FAKE_SKIP', '')
    attempts = pathlib.Path(os.environ['FAKE_LOG']).read_text().count('--query-file')
    for s in scenes:
        if s == skip and attempts < 99 and not os.environ.get('FAKE_FIX_ON_RETRY'):
            continue
        if s == skip and os.environ.get('FAKE_FIX_ON_RETRY') and 'Continuation' not in q:
            continue
        d.setdefault('scene_progress', {})[s] = {'say_draft': 'built', 'layout_review': 'passed'}
    if not scenes:
        d['state'] = 'draft'; d['completed'] = ['notes', 'storyboard', 'script', 'code', 'draft_review']
    ck.write_text(yaml.safe_dump(d))
    print('done'); print(); print('session_id: local-fake-%d' % attempts)
    """)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.root = Path(self.tmp.name)
        self.sec = make_section(self.root)
        self.hermes = self.root / "hermes"
        worker = self.root / "fake_worker.py"
        worker.write_text(FAKE_HERMES)
        self.hermes.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(worker))} "$@"\n')
        self.hermes.chmod(self.hermes.stat().st_mode | stat.S_IEXEC)
        self.usage = self.root / "usage.json"
        self.set_usage(10, 10)
        self.log = self.root / "calls.log"
        self.env = dict(os.environ, FAKE_LOG=str(self.log))

    def tearDown(self):
        self.tmp.cleanup()

    def set_usage(self, session, week):
        self.usage.write_text(json.dumps({"windows": [{"label": "Current session", "used_percent": session},
                                                      {"label": "Current week", "used_percent": week}]}))

    def run_(self, **kw):
        kw.setdefault("hermes", str(self.hermes))
        kw.setdefault("usage_cmd", ["cat", str(self.usage)])
        kw.setdefault("env", self.env)
        kw.setdefault("static_check", lambda section, scenes: [])
        return wo.run(self.sec, **kw)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_runs_each_order_then_consistency_with_lean_flags(self):
        result = self.run_()
        self.assertEqual(result["status"], "done")
        runs0 = [json.loads(l) for l in (self.sec / "build" / "workorders" / "runs.jsonl").read_text().splitlines()]
        for key in ("tokens", "context", "tools", "review", "section"):
            self.assertIn(key, runs0[0])                              # telemetry fields always present
        self.assertEqual(runs0[0]["section"], "05-teardown")
        calls = self.calls()
        self.assertEqual(len(calls), 4)                               # 3 scenes + consistency
        first = calls[0]
        for flag in ("-Q", "--ignore-rules", "--max-turns", "--source tool", "-t terminal,file,vision",
                     "--provider anthropic", "-m claude-sonnet-5-5", "--reasoning high"):
            self.assertIn(flag, first)
        self.assertIn("--reasoning medium", calls[-1])                # consistency pass is cheaper
        runs = [json.loads(l) for l in (self.sec / "build" / "workorders" / "runs.jsonl").read_text().splitlines()]
        self.assertEqual([r["session_id"] for r in runs][:2], ["local-fake-1", "local-fake-2"])
        self.assertTrue(all(r["outcome"] == "success" for r in runs))

    def test_resume_skips_scenes_already_done(self):
        ck = yaml.safe_load((self.sec / "checkpoint.yaml").read_text())
        ck["scene_progress"] = {"WhyClose": {"say_draft": "built", "layout_review": "passed"}}
        (self.sec / "checkpoint.yaml").write_text(yaml.safe_dump(ck))
        self.run_()
        self.assertEqual(len(self.calls()), 3)
        self.assertFalse(any("01-WhyClose" in c for c in self.calls()))

    def test_incomplete_scene_gets_one_continuation_then_stops(self):
        self.env["FAKE_SKIP"] = "FinHandshake"
        result = self.run_()
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["order"], "02-FinHandshake")
        attempts = [c for c in self.calls() if "02-FinHandshake" in c]
        self.assertEqual(len(attempts), 2)
        self.assertIn("--reasoning high", attempts[0])
        self.assertIn("--reasoning medium", attempts[1])                # fix-only continuation
        self.assertEqual(len(self.calls()), 3)                       # never reached TimeWait

    def test_continuation_can_finish_the_scene(self):
        self.env.update(FAKE_SKIP="FinHandshake", FAKE_FIX_ON_RETRY="1")
        self.assertEqual(self.run_()["status"], "done")

    def test_pauses_before_an_order_when_usage_is_high(self):
        self.set_usage(81, 50)
        result = self.run_()
        self.assertEqual(result["status"], "paused")
        self.assertEqual(self.calls(), [])
        self.set_usage(10, 92)
        self.assertEqual(self.run_()["status"], "paused")

    def test_quota_error_pauses_instead_of_retrying(self):
        self.env["FAKE_QUOTA"] = "1"
        result = self.run_()
        self.assertEqual(result["status"], "paused")
        self.assertEqual(len(self.calls()), 1)

    def test_unexplained_static_speech_triggers_a_continuation_listing_the_blocks(self):
        def check(section, scenes):
            ck = yaml.safe_load((section / "checkpoint.yaml").read_text()) or {}
            holds = ck.get("justified_static_holds") or []
            flagged = ["FinHandshake [02]", "FinHandshake [04]"] if "FinHandshake" in scenes else []
            return [f for f in flagged if not any(h.startswith(f) for h in holds)]
        seen = []
        orig = wo.render_order
        def spy(section, scenes, index, total, call_budget=25, continuation=False, static_lines=None):
            seen.append((scenes, continuation, list(static_lines or [])))
            return orig(section, scenes, index, total, call_budget, continuation, static_lines)
        wo.render_order = spy
        try:
            result = self.run_(static_check=check)
        finally:
            wo.render_order = orig
        self.assertEqual(result["status"], "incomplete")
        self.assertIn((["FinHandshake"], True, ["FinHandshake [02]", "FinHandshake [04]"]), seen)

    def test_holds_recorded_by_the_worker_satisfy_the_static_gate(self):
        ck = yaml.safe_load((self.sec / "checkpoint.yaml").read_text())
        ck["justified_static_holds"] = ["FinHandshake [02]: reading hold on the trace table",
                                        "FinHandshake [04]: reading hold"]
        (self.sec / "checkpoint.yaml").write_text(yaml.safe_dump(ck))
        def check(section, scenes):
            holds = (yaml.safe_load((section / "checkpoint.yaml").read_text()) or {}).get("justified_static_holds") or []
            flagged = ["FinHandshake [02]", "FinHandshake [04]"] if "FinHandshake" in scenes else []
            return [f for f in flagged if not any(h.startswith(f) for h in holds)]
        self.assertEqual(self.run_(static_check=check)["status"], "done")

    def test_static_lines_from_narrate_json_map_to_scene_blocks(self):
        report = {"lines": [{"scene": "A", "static_speech": False}, {"scene": "A", "static_speech": True},
                            {"scene": "B", "static_speech": True}]}
        self.assertEqual(wo.static_blocks(report, ["A"]), ["A [02]"])
        self.assertEqual(wo.static_blocks(report, ["A", "B"]), ["A [02]", "B [01]"])

    def test_cli_limit_flags_reach_the_runner(self):
        seen = {}
        orig = wo.run
        wo.run = lambda section, **kw: seen.update(kw) or {"status": "done"}
        try:
            wo.main([str(self.sec), "--session-limit", "95", "--week-limit", "101"])
        finally:
            wo.run = orig
        self.assertEqual((seen["session_limit"], seen["week_limit"]), (95.0, 101.0))

    def test_dry_run_writes_orders_and_calls_nothing(self):
        result = self.run_(dry_run=True)
        self.assertEqual(result["status"], "dry-run")
        self.assertEqual(self.calls(), [])
        self.assertTrue((self.sec / "build" / "workorders" / "01-WhyClose.md").exists())
        self.assertTrue((self.sec / "build" / "workorders" / "04-consistency.md").exists())


if __name__ == "__main__":
    unittest.main()
