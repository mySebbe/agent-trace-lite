"""CLI entry point for agent-trace-lite."""

from __future__ import annotations

import argparse
import sys

from ._version import __version__
from .trace import (
    DEFAULT_MAX_INPUT_BYTES,
    DEFAULT_MAX_LINE_BYTES,
    TraceRecorder,
    render_summary,
    render_validation,
    summarize_trace,
    validate_trace,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise ValueError("must be at least 1")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError("must not be negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and summarize lightweight agent JSONL traces.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Append a span_start record.")
    start.add_argument("path")
    start.add_argument("name")
    start.add_argument("--span-id")
    start.add_argument("--parent-id")

    end = subparsers.add_parser("end", help="Append a span_end record.")
    end.add_argument("path")
    end.add_argument("span_id")
    end.add_argument("--status", default="ok", choices=("ok", "error"))
    end.add_argument("--error")

    event = subparsers.add_parser("event", help="Append an event record.")
    event.add_argument("path")
    event.add_argument("name")
    event.add_argument("--span-id")
    event.add_argument("--level", default="info", choices=("info", "warning", "error"))
    event.add_argument("--message")

    summary = subparsers.add_parser("summary", help="Summarize a trace file.")
    summary.add_argument("path")
    summary.add_argument("--format", choices=("text", "json", "markdown"), default="text")

    validate = subparsers.add_parser("validate", help="Validate JSONL syntax and span lifecycle.")
    validate.add_argument("path")
    validate.add_argument("--format", choices=("json", "text"), default="json")
    validate.add_argument(
        "--max-line-bytes",
        type=_positive_int,
        default=DEFAULT_MAX_LINE_BYTES,
        help=f"Maximum physical line size including its line ending (default: {DEFAULT_MAX_LINE_BYTES}).",
    )
    validate.add_argument(
        "--max-input-bytes",
        type=_non_negative_int,
        default=DEFAULT_MAX_INPUT_BYTES,
        help=f"Maximum total input size (default: {DEFAULT_MAX_INPUT_BYTES}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        recorder = TraceRecorder(args.path) if args.command in {"start", "end", "event"} else None
        if args.command == "start":
            span_id = recorder.start_span(args.name, span_id=args.span_id, parent_id=args.parent_id)
            print(span_id)
        elif args.command == "end":
            recorder.end_span(args.span_id, status=args.status, error=args.error)
        elif args.command == "event":
            recorder.event(args.name, span_id=args.span_id, level=args.level, message=args.message)
        elif args.command == "summary":
            sys.stdout.write(render_summary(summarize_trace(args.path), args.format))
        elif args.command == "validate":
            result = validate_trace(
                args.path,
                max_line_bytes=args.max_line_bytes,
                max_input_bytes=args.max_input_bytes,
            )
            sys.stdout.write(render_validation(result, args.format))
            return 0 if result["valid"] else 1
        else:
            parser.error("unknown command")
    except OSError as exc:
        print(f"agent-trace-lite: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
