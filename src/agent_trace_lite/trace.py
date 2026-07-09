"""Record and summarize simple JSONL agent traces."""

from __future__ import annotations

import json
import math
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

DEFAULT_MAX_LINE_BYTES = 1024 * 1024
DEFAULT_MAX_INPUT_BYTES = 16 * 1024 * 1024
_RECORD_TYPES = {"event", "span_end", "span_start"}


def _now() -> float:
    return time.time()


def _iter_bounded_lines(
    handle: BinaryIO,
    *,
    max_line_bytes: int,
    max_input_bytes: int,
) -> Iterator[tuple[int, bytes, bool, bool, int]]:
    """Yield bounded physical lines without buffering an untrusted whole file."""
    total_bytes = 0
    line_number = 1
    line = bytearray()
    line_size = 0

    while True:
        remaining = max_input_bytes - total_bytes
        chunk = handle.read(min(8192, remaining + 1))
        if not chunk:
            if line_size:
                yield line_number, bytes(line), line_size > max_line_bytes, False, total_bytes
            return
        if len(chunk) > remaining:
            total_bytes += len(chunk)
            yield line_number, b"", False, True, total_bytes
            return

        total_bytes += len(chunk)
        for byte in chunk:
            line_size += 1
            if byte == 0x0A:
                too_large = line_size > max_line_bytes
                yield line_number, b"" if too_large else bytes(line), too_large, False, total_bytes
                line_number += 1
                line = bytearray()
                line_size = 0
            elif len(line) < max_line_bytes:
                line.append(byte)


class _NonFiniteNumber(ValueError):
    """Raised when JSON contains a non-finite number."""


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteNumber(value)
    return parsed


def _reject_json_constant(value: str) -> None:
    raise _NonFiniteNumber(value)


def _is_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _diagnostic(
    line: int,
    code: str,
    message: str,
    **details: object,
) -> dict[str, object]:
    return {"line": line, "code": code, "message": message, **details}


def _require_string(
    record: dict[str, Any],
    field: str,
    line: int,
    diagnostics: list[dict[str, object]],
    *,
    allow_empty: bool = False,
) -> str | None:
    if field not in record:
        diagnostics.append(
            _diagnostic(line, "missing_field", "Required field is missing.", field=field)
        )
        return None
    value = record[field]
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        diagnostics.append(
            _diagnostic(line, "invalid_field", "Field must be a non-empty string.", field=field)
        )
        return None
    return value


def _optional_string(
    record: dict[str, Any],
    field: str,
    line: int,
    diagnostics: list[dict[str, object]],
) -> bool:
    if field in record and not isinstance(record[field], str):
        diagnostics.append(
            _diagnostic(line, "invalid_field", "Field must be a string when present.", field=field)
        )
        return False
    return True


def _require_number(
    record: dict[str, Any],
    field: str,
    line: int,
    diagnostics: list[dict[str, object]],
) -> bool:
    if field not in record:
        diagnostics.append(
            _diagnostic(line, "missing_field", "Required field is missing.", field=field)
        )
        return False
    if not _is_number(record[field]):
        diagnostics.append(
            _diagnostic(line, "invalid_field", "Field must be a finite number.", field=field)
        )
        return False
    return True


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


def validate_trace(
    path: str | Path,
    *,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
) -> dict[str, Any]:
    """Validate JSONL syntax, record fields, and span lifecycle state.

    The validator reads at most ``max_input_bytes + 1`` bytes and retains at most
    ``max_line_bytes`` bytes for any individual line. Diagnostic output never
    includes the original line contents.
    """
    if max_line_bytes < 1:
        raise ValueError("max_line_bytes must be at least 1")
    if max_input_bytes < 0:
        raise ValueError("max_input_bytes must not be negative")

    diagnostics: list[dict[str, object]] = []
    started: dict[str, int] = {}
    ended: set[str] = set()
    bytes_read = 0
    lines_checked = 0
    records_checked = 0

    with Path(path).open("rb") as handle:
        for line_number, data, line_too_large, input_too_large, scanned_bytes in _iter_bounded_lines(
            handle,
            max_line_bytes=max_line_bytes,
            max_input_bytes=max_input_bytes,
        ):
            bytes_read = scanned_bytes
            if input_too_large:
                diagnostics.append(
                    _diagnostic(
                        line_number,
                        "input_too_large",
                        "Input exceeds the configured byte limit.",
                        limit=max_input_bytes,
                    )
                )
                break

            lines_checked += 1
            if line_too_large:
                diagnostics.append(
                    _diagnostic(
                        line_number,
                        "line_too_large",
                        "Line exceeds the configured byte limit.",
                        limit=max_line_bytes,
                    )
                )
                continue
            if not data.strip():
                continue

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                diagnostics.append(
                    _diagnostic(line_number, "invalid_utf8", "Line is not valid UTF-8.")
                )
                continue

            try:
                value = json.loads(
                    text,
                    parse_constant=_reject_json_constant,
                    parse_float=_parse_finite_float,
                )
            except _NonFiniteNumber:
                diagnostics.append(
                    _diagnostic(line_number, "non_finite_number", "JSON contains a non-finite number.")
                )
                continue
            except json.JSONDecodeError:
                diagnostics.append(
                    _diagnostic(line_number, "malformed_json", "Line is not valid JSON.")
                )
                continue
            except RecursionError:
                diagnostics.append(
                    _diagnostic(line_number, "json_too_deep", "JSON nesting exceeds parser limits.")
                )
                continue

            if not isinstance(value, dict):
                diagnostics.append(
                    _diagnostic(line_number, "record_not_object", "JSON record must be an object.")
                )
                continue
            records_checked += 1

            record_type = value.get("type")
            if "type" not in value:
                diagnostics.append(
                    _diagnostic(line_number, "missing_field", "Required field is missing.", field="type")
                )
                continue
            if not isinstance(record_type, str):
                diagnostics.append(
                    _diagnostic(line_number, "invalid_field", "Field must be a string.", field="type")
                )
                continue
            if record_type not in _RECORD_TYPES:
                diagnostics.append(
                    _diagnostic(
                        line_number,
                        "unknown_record_type",
                        "Record type is not supported by the trace schema.",
                        field="type",
                    )
                )
                continue

            timestamp_valid = _require_number(value, "timestamp", line_number, diagnostics)

            if record_type == "span_start":
                span_id = _require_string(value, "span_id", line_number, diagnostics)
                name = _require_string(value, "name", line_number, diagnostics)
                parent_valid = _optional_string(value, "parent_id", line_number, diagnostics)
                if timestamp_valid and span_id is not None and name is not None and parent_valid:
                    if span_id in started:
                        diagnostics.append(
                            _diagnostic(
                                line_number,
                                "duplicate_span_start",
                                "Span has more than one span_start record.",
                                span_id=span_id,
                                first_line=started[span_id],
                            )
                        )
                    else:
                        started[span_id] = line_number
            elif record_type == "span_end":
                span_id = _require_string(value, "span_id", line_number, diagnostics)
                status = _require_string(value, "status", line_number, diagnostics)
                duration_valid = True
                if "duration_ms" in value:
                    duration_valid = _is_number(value["duration_ms"]) and value["duration_ms"] >= 0
                    if not duration_valid:
                        diagnostics.append(
                            _diagnostic(
                                line_number,
                                "invalid_field",
                                "Field must be a non-negative finite number.",
                                field="duration_ms",
                            )
                        )
                error_valid = _optional_string(value, "error", line_number, diagnostics)
                if (
                    timestamp_valid
                    and span_id is not None
                    and status is not None
                    and duration_valid
                    and error_valid
                ):
                    if span_id not in started:
                        diagnostics.append(
                            _diagnostic(
                                line_number,
                                "span_end_without_start",
                                "span_end has no preceding span_start record.",
                                span_id=span_id,
                            )
                        )
                    elif span_id in ended:
                        diagnostics.append(
                            _diagnostic(
                                line_number,
                                "duplicate_span_end",
                                "Span has more than one span_end record.",
                                span_id=span_id,
                            )
                        )
                    else:
                        ended.add(span_id)
            else:
                _require_string(value, "name", line_number, diagnostics)
                _require_string(value, "level", line_number, diagnostics)
                _optional_string(value, "span_id", line_number, diagnostics)
                _optional_string(value, "message", line_number, diagnostics)

    for span_id, start_line in started.items():
        if span_id not in ended:
            diagnostics.append(
                _diagnostic(
                    start_line,
                    "open_span",
                    "Span has no matching span_end record.",
                    span_id=span_id,
                )
            )

    diagnostics.sort(
        key=lambda item: (
            int(item["line"]),
            str(item["code"]),
            str(item.get("field", "")),
            str(item.get("span_id", "")),
        )
    )
    return {
        "valid": not diagnostics,
        "diagnostics": diagnostics,
        "limits": {
            "max_input_bytes": max_input_bytes,
            "max_line_bytes": max_line_bytes,
        },
        "stats": {
            "bytes_read": bytes_read,
            "lines_checked": lines_checked,
            "records_checked": records_checked,
        },
    }


def render_validation(result: dict[str, Any], output_format: str = "json") -> str:
    """Render validator output as deterministic JSON or concise text."""
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output_format != "text":
        raise ValueError(f"unsupported output format: {output_format}")
    lines = [
        f"valid={str(result['valid']).lower()} "
        f"lines_checked={result['stats']['lines_checked']} "
        f"records_checked={result['stats']['records_checked']} "
        f"diagnostics={len(result['diagnostics'])}"
    ]
    lines.extend(
        f"line={item['line']} code={item['code']} message={item['message']}"
        for item in result["diagnostics"]
    )
    return "\n".join(lines) + "\n"


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
