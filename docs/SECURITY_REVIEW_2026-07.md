# Security Review: 2026-07

## Scope

This review covers the JSONL trace reader, the new `validate` command, and the existing `TraceRecorder` and `summary` workflows. Trace files may contain prompts, tool arguments, error messages, and other sensitive agent context.

## Executive Summary

The validation path now uses bounded binary streaming, rejects malformed input without echoing trace contents, and returns deterministic machine-readable diagnostics. Duplicate and invalid span lifecycle transitions are reported instead of being silently accepted. No high-severity issue was identified in the reviewed validation path.

## Findings

### S-01: Unbounded JSONL reads in legacy summary path

**Severity:** Medium

**Status:** Open, documented residual risk

The legacy `_iter_records` path used by `summary` reads a file line-by-line without configurable line or total-input limits. A hostile or accidentally oversized trace can therefore consume more memory than the bounded validation path. The new `validate` command is the recommended pre-ingestion gate. The recorder also intentionally remains append-oriented and does not impose a total trace quota.

**Relevant code:** `src/agent_trace_lite/trace.py:458-473` (`_iter_records`) and `src/agent_trace_lite/trace.py:485-487` (`summarize_trace`).

**Recommendation:** Add the same limits to summary when a backwards-compatible API design is available, or require callers to validate traces before summarizing untrusted files.

### S-02: Trace contents are sensitive data

**Severity:** Medium

**Status:** Mitigated by documentation

Trace records can include prompts, tool arguments, and errors. Validation diagnostics intentionally contain only line numbers, stable codes, field names, limits, and span IDs needed to identify lifecycle failures; they do not include original line text. Operators must still protect trace files at rest and redact them before sharing, as described in `SECURITY.md`.

## Controls Implemented

- `validate_trace` reads at most one byte beyond the configured total input limit and retains at most the configured line limit while scanning (`src/agent_trace_lite/trace.py:22-56`, `src/agent_trace_lite/trace.py:222-436`).
- The CLI defaults to a 1 MiB line limit and a 16 MiB input limit, both configurable for trusted workloads (`src/agent_trace_lite/__main__.py:62-101`).
- Malformed JSON, invalid UTF-8, non-object records, unknown types, field errors, and non-finite numbers use stable diagnostic codes and messages.
- Duplicate starts, duplicate ends, ends without starts, and spans left open at end-of-file are detected.
- Validation returns JSON by default and uses exit code `0` for valid traces, `1` for invalid traces, and `2` for operational or argument errors.

## Verification

- `python -m unittest discover -s tests`: 8 tests passed.
- `python -m ruff check .`: passed.
- `python -m bandit -r src -q`: passed with no findings.
- `python -m pip_audit`: no known vulnerabilities found; the environment tool skipped `smolagents 1.27.0.dev0` because it is not available on PyPI.
- `python -m build --sdist --wheel`: sdist and wheel built successfully.
