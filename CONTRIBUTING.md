# Contributing

## Local Setup

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

## Guidelines

- Keep the JSONL format readable and append-only.
- Preserve backwards-compatible record fields when possible.
- Add tests for CLI and summary behavior.
- Avoid network calls in tests.

Release instructions live in [PUBLISHING.md](PUBLISHING.md).
