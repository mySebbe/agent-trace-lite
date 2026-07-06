"""Record and summarize simple JSONL agent traces."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def _now() -> float:
    return time.time()


class TraceRecorder:
    """Append span and event records to a JSONL trace file."""

    def __init__(self, path: str):
        self.path = Path(path)

    def _append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def start_span(
        self,
        name: str,
        *,
        span_id: str | None = None,
        parent_id: str | None = None,
        timestamp: float | None = None,
    ) -> str:
        span_id = span_id or uuid.uuid4().hex
        record: dict[str, Any] = {
            "type": "span_start",
            "span_id": span_id,
            "name": name,
            "timestamp": _now() if timestamp is None else timestamp,
        }
        if parent_id:
            record["parent_id"] = parent_id
        self._append(record)
        return span_id

    def event(
        self,
        name: str,
        *,
        span_id: str | None = None,
        level: str = "info",
        message: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "type": "event",
            "name": name,
            "level": level,
            "timestamp": _now() if timestamp is None else timestamp,
        }
        if span_id:
            record["span_id"] = span_id
        if message:
            record["message"] = message
        self._append(record)

    def end_span(
        self,
        span_id: str,
        *,
        status: str = "ok",
        error: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        ended_at = _now() if timestamp is None else timestamp
        started_at = _find_span_start(self.path, span_id)
        record: dict[str, Any] = {
            "type": "span_end",
            "span_id": span_id,
            "status": status,
            "timestamp": ended_at,
        }
        if started_at is not None:
            record["duration_ms"] = max(0, round((ended_at - started_at) * 1000))
        if error:
            record["error"] = error
        self._append(record)


def _iter_records(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return records
    with file_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def _find_span_start(path: Path, span_id: str) -> float | None:
    for record in reversed(_iter_records(path)):
        if record.get("type") == "span_start" and record.get("span_id") == span_id:
            timestamp = record.get("timestamp")
            if isinstance(timestamp, (int, float)):
                return float(timestamp)
    return None


def summarize_trace(path: str) -> dict[str, Any]:
    """Summarize spans, events, errors, and completed span durations."""
    records = _iter_records(path)
    started_ids = {
        str(record.get("span_id"))
        for record in records
        if record.get("type") == "span_start" and record.get("span_id")
    }
    ended_ids = {
        str(record.get("span_id"))
        for record in records
        if record.get("type") == "span_end" and record.get("span_id")
    }
    event_levels: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    spans = sum(1 for record in records if record.get("type") == "span_start")
    events = 0
    for record in records:
        if record.get("type") == "event":
            events += 1
            level = str(record.get("level") or "info")
            event_levels[level] = event_levels.get(level, 0) + 1
    ended = [record for record in records if record.get("type") == "span_end"]
    for record in ended:
        status = str(record.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    errors = sum(1 for record in records if record.get("type") == "event" and record.get("level") == "error")
    errors += sum(1 for record in ended if record.get("status") == "error" or bool(record.get("error")))
    durations = [record.get("duration_ms") for record in ended if isinstance(record.get("duration_ms"), (int, float))]
    total_duration = int(sum(durations))
    timestamps = [
        float(record["timestamp"])
        for record in records
        if isinstance(record.get("timestamp"), (int, float))
    ]
    first_timestamp = min(timestamps) if timestamps else None
    last_timestamp = max(timestamps) if timestamps else None
    return {
        "spans": spans,
        "completed_spans": len(ended),
        "open_spans": len(started_ids - ended_ids),
        "events": events,
        "errors": errors,
        "event_levels": dict(sorted(event_levels.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "total_duration_ms": total_duration,
        "max_duration_ms": int(max(durations)) if durations else 0,
        "avg_duration_ms": int(round(total_duration / len(durations))) if durations else 0,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "wall_time_ms": int(round((last_timestamp - first_timestamp) * 1000))
        if first_timestamp is not None and last_timestamp is not None
        else 0,
    }


def render_summary(summary: dict[str, Any], output_format: str = "text") -> str:
    if output_format == "json":
        return json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if output_format == "markdown":
        rows = [
            ("Spans", summary["spans"]),
            ("Completed spans", summary["completed_spans"]),
            ("Open spans", summary.get("open_spans", 0)),
            ("Events", summary["events"]),
            ("Errors", summary["errors"]),
            ("Total span duration", f"{summary['total_duration_ms']} ms"),
            ("Average span duration", f"{summary.get('avg_duration_ms', 0)} ms"),
            ("Wall time", f"{summary.get('wall_time_ms', 0)} ms"),
        ]
        lines = ["# Agent Trace Summary", "", "| Metric | Value |", "| --- | --- |"]
        lines.extend(f"| {name} | {value} |" for name, value in rows)
        return "\n".join(lines) + "\n"
    if output_format != "text":
        raise ValueError(f"unsupported output format: {output_format}")
    return (
        f"spans={summary['spans']} completed={summary['completed_spans']} "
        f"open={summary.get('open_spans', 0)} events={summary['events']} "
        f"errors={summary['errors']} total_duration_ms={summary['total_duration_ms']} "
        f"avg_duration_ms={summary.get('avg_duration_ms', 0)} "
        f"wall_time_ms={summary.get('wall_time_ms', 0)}\n"
    )
