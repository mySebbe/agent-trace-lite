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
```

Record types:

- `span_start`: span id, name, timestamp, optional parent id
- `event`: name, timestamp, level, optional message and span id
- `span_end`: span id, status, timestamp, and duration when the start record is present

## Development

```bash
python -m unittest discover -s tests
```
