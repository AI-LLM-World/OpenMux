"""Core functionality for OpenCascade.

Expose Orchestrator and TaskType lazily to avoid importing providers and
their heavy optional dependencies at package import time.
"""

__all__ = ["Orchestrator", "TaskType"]


def __getattr__(name: str):
    if name == "Orchestrator":
        from .orchestrator import Orchestrator as _Orch

        return _Orch
    if name == "TaskType":
        from .orchestrator import TaskType as _TT

        return _TT
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
