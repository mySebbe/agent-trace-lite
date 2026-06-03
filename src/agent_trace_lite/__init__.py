"""Lightweight JSONL tracing for agent workflows."""

from .trace import TraceRecorder, summarize_trace

__all__ = ["__version__", "TraceRecorder", "summarize_trace"]
from ._version import __version__
