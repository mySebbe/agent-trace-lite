# agent-trace-lite

`agent-trace-lite` records simple agent spans and events to JSONL and summarizes durations and errors.

## 0.1.2 Highlights

- Trace summaries now include first timestamp, last timestamp, and wall-clock runtime.
- `summary --format markdown` emits a paste-ready Markdown table for issues, PRs, and release notes.

## Install

```bash
python -m pip install .
```

## CLI

```bash
agent-trace-lite start trace.jsonl plan
agent-trace-lite event trace.jsonl tool_call --message "ran command"
agent-trace-lite end trace.jsonl SPAN_ID --status ok
agent-trace-lite summary trace.jsonl --format json
agent-trace-lite summary trace.jsonl --format markdown
agent-trace-lite validate trace.jsonl
```

Record types:

- `span_start`: span id, name, timestamp, optional parent id
- `event`: name, timestamp, level, optional message and span id
- `span_end`: span id, status, timestamp, and duration when the start record is present

## Validate Traces

`validate` reads JSONL as a bounded byte stream and emits deterministic JSON by default. It checks UTF-8 and JSON syntax, supported record fields, and span lifecycle errors such as duplicate starts, duplicate ends, ends without starts, and open spans.

```bash
agent-trace-lite validate trace.jsonl --format json
agent-trace-lite validate trace.jsonl --max-line-bytes 1048576 --max-input-bytes 16777216
```

The default maximum physical line size is 1 MiB and the default total input limit is 16 MiB. Both limits are byte-based; the line limit includes its line ending when present. The validator retains no original line contents in diagnostics. Exit code `0` means valid, `1` means the trace is invalid, and `2` means the file could not be read or the command arguments are invalid.

## Development

```bash
python -m unittest discover -s tests
```
