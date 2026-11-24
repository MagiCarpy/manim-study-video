"""Work-order telemetry: each runs.jsonl row carries tokens, context growth, tool counts and review result,
measured locally right after the worker exits (agent.log rotates, workers don't self-report)."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from studio import workorders as wo

LOG = """\
2026-11-18 10:00:01,000 INFO [sid-1] agent.conversation_loop: API call #1: model=claude-sonnet-5-5 provider=anthropic in=12000 out=300 total=12300 latency=2s write=11990 id=m1
2026-11-18 10:00:05,000 INFO [other] agent.conversation_loop: API call #1: model=x provider=y in=999999 out=1 total=1 latency=1s id=z
2026-11-18 10:00:09,000 INFO [sid-1] agent.conversation_loop: API call #2: model=claude-sonnet-5-5 provider=anthropic in=20000 out=500 total=20500 latency=2s cache=12000/20000 (60%) write=8000 id=m2
2026-11-18 10:00:19,000 INFO [sid-1] agent.conversation_loop: API call #3: model=claude-sonnet-5-5 provider=anthropic in=26000 out=100 total=26100 latency=2s cache=20000/26000 (77%) write=6000 id=m3
"""


def tool_call(name, **args):
    return {"type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class WorkerRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.home = Path(self.tmp.name)
        (self.home / "logs").mkdir()
        (self.home / "logs" / "agent.log.1").write_text(LOG)
        with sqlite3.connect(self.home / "state.db") as c:
            c.execute("CREATE TABLE sessions (id TEXT, api_call_count INT, input_tokens INT, output_tokens INT, "
                      "cache_read_tokens INT, cache_write_tokens INT, reasoning_tokens INT)")
            c.execute("INSERT INTO sessions VALUES ('sid-1', 3, 30, 900, 32000, 25990, 0)")
            c.execute("CREATE TABLE messages (session_id TEXT, role TEXT, tool_calls TEXT, timestamp REAL)")
            calls = [[tool_call("terminal", command='"$STUDY" build $S --engine say --scene A')],
                     [tool_call("terminal", command='"$STUDY" review $S --lint --layout --scene A'),
                      tool_call("vision_analyze", image_url="x.png")],
                     [tool_call("patch", path="scenes.py")],
                     [tool_call("terminal", command='"$STUDY" build $S --engine say --scene A'),
                      tool_call("terminal", command='"$STUDY" review $S --lint --layout --scene A; "$STUDY" narrate $S --check')]]
            for i, tc in enumerate(calls):
                c.execute("INSERT INTO messages VALUES ('sid-1', 'assistant', ?, ?)", (json.dumps(tc), i))

    def tearDown(self):
        self.tmp.cleanup()

    def test_tokens_context_and_tools_for_one_session(self):
        r = wo.worker_record("sid-1", home=self.home)
        self.assertEqual(r["tokens"], {"api_call_count": 3, "input_tokens": 30, "output_tokens": 900,
                                       "cache_read_tokens": 32000, "cache_write_tokens": 25990, "reasoning_tokens": 0})
        self.assertEqual(r["context"], {"calls": 3, "first": 12000, "peak": 26000, "sum": 58000})
        self.assertEqual(r["tools"]["builds"], 2)
        self.assertEqual(r["tools"]["reviews"], 2)
        self.assertEqual(r["tools"]["narrate_checks"], 1)
        self.assertEqual(r["tools"]["vision"], 1)
        self.assertEqual(r["tools"]["patch"], 1)

    def test_unknown_or_missing_data_is_none_not_zero(self):
        r = wo.worker_record("nope", home=self.home)
        self.assertIsNone(r["tokens"])
        self.assertIsNone(r["context"])
        r = wo.worker_record(None, home=self.home)
        self.assertEqual(r, {"tokens": None, "context": None, "tools": None})
        r = wo.worker_record("sid-1", home=self.home / "absent")
        self.assertIsNone(r["tokens"])

    def test_review_record_reads_the_last_report(self):
        s = self.home / "sec"
        (s / "build" / "review").mkdir(parents=True)
        self.assertIsNone(wo.review_record(s))
        (s / "build" / "review" / "report.json").write_text(json.dumps({
            "status": "FAIL", "errors": 1, "warnings": 2,
            "issues": [{"code": "text_overlap", "severity": "error"}, {"code": "source_tag_gap", "severity": "warning"},
                       {"code": "source_tag_gap", "severity": "warning"}]}))
        self.assertEqual(wo.review_record(s), {"status": "FAIL", "errors": 1, "warnings": 2,
                                               "codes": {"text_overlap": 1, "source_tag_gap": 2}})


if __name__ == "__main__":
    unittest.main()
