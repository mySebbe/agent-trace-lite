import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_trace_lite.trace import TraceRecorder, render_summary, summarize_trace


class TraceTests(unittest.TestCase):
    def test_recorder_writes_span_and_event_jsonl(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        recorder = TraceRecorder(path)
        span_id = recorder.start_span("plan", timestamp=10.0)
        recorder.event("tool_call", span_id=span_id, message="ran command", timestamp=11.0)
        recorder.end_span(span_id, status="ok", timestamp=12.5)

        with open(path, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]

        self.assertEqual(rows[0]["type"], "span_start")
        self.assertEqual(rows[1]["type"], "event")
        self.assertEqual(rows[2]["duration_ms"], 2500)

    def test_summarize_trace_counts_spans_events_errors_and_duration(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "span_start", "span_id": "a", "name": "plan", "timestamp": 1.0}) + "\n")
            handle.write(json.dumps({"type": "span_start", "span_id": "b", "name": "left-open", "timestamp": 1.5}) + "\n")
            handle.write(json.dumps({"type": "event", "level": "error", "timestamp": 2.0, "name": "boom"}) + "\n")
            handle.write(json.dumps({"type": "event", "level": "info", "timestamp": 2.2, "name": "note"}) + "\n")
            handle.write(json.dumps({"type": "span_end", "span_id": "a", "status": "error", "timestamp": 3.25, "duration_ms": 2250}) + "\n")
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        summary = summarize_trace(path)

        self.assertEqual(summary["spans"], 2)
        self.assertEqual(summary["completed_spans"], 1)
        self.assertEqual(summary["open_spans"], 1)
        self.assertEqual(summary["events"], 2)
        self.assertEqual(summary["errors"], 2)
        self.assertEqual(summary["event_levels"], {"error": 1, "info": 1})
        self.assertEqual(summary["status_counts"], {"error": 1})
        self.assertEqual(summary["total_duration_ms"], 2250)
        self.assertEqual(summary["avg_duration_ms"], 2250)
        self.assertEqual(summary["first_timestamp"], 1.0)
        self.assertEqual(summary["last_timestamp"], 3.25)
        self.assertEqual(summary["wall_time_ms"], 2250)

    def test_markdown_summary_is_table_shaped(self):
        rendered = render_summary(
            {
                "spans": 1,
                "completed_spans": 1,
                "open_spans": 0,
                "events": 2,
                "errors": 0,
                "total_duration_ms": 500,
                "avg_duration_ms": 500,
                "wall_time_ms": 750,
            },
            "markdown",
        )

        self.assertIn("# Agent Trace Summary", rendered)
        self.assertIn("| Wall time | 750 ms |", rendered)

    def test_cli_summary_outputs_json(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "span_start", "span_id": "a", "name": "plan", "timestamp": 1.0}) + "\n")
            handle.write(json.dumps({"type": "span_end", "span_id": "a", "status": "ok", "timestamp": 2.0, "duration_ms": 1000}) + "\n")
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))

        completed = subprocess.run(
            [sys.executable, "-m", "agent_trace_lite", "summary", path, "--format", "json"],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["total_duration_ms"], 1000)
        self.assertEqual(json.loads(completed.stdout)["wall_time_ms"], 1000)


if __name__ == "__main__":
    unittest.main()
