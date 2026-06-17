"""Version helpers for agent-trace-lite."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

_DISTRIBUTION_NAME = "agent-trace-lite"

try:
    __version__ = _distribution_version(_DISTRIBUTION_NAME)
except PackageNotFoundError:
    __version__ = "0.1.1"
