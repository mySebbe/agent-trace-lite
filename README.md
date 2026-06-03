# agent-trace-lite

`agent-trace-lite` records simple agent spans and events to JSONL and summarizes durations and errors.

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
```

Record types:

- `span_start`: span id, name, timestamp, optional parent id
- `event`: name, timestamp, level, optional message and span id
- `span_end`: span id, status, timestamp, and duration when the start record is present

## Development

```bash
python -m unittest discover -s tests
```
