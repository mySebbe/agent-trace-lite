"""CLI entry point for agent-trace-lite."""

from __future__ import annotations

import argparse
import sys

from ._version import __version__
from .trace import TraceRecorder, render_summary, summarize_trace


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
    summary.add_argument("--format", choices=("text", "json"), default="text")
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
        else:
            parser.error("unknown command")
    except OSError as exc:
        print(f"agent-trace-lite: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
