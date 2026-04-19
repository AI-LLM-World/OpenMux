"""
OpenMux - Free Multi-Source GenAI Orchestration Library

A Python library for automatic model selection and routing across free GenAI providers.
"""

import os
from pathlib import Path

# Auto-load .env file if it exists
try:
    from dotenv import load_dotenv
    
    # Look for .env in current directory and parent directories
    current_dir = Path.cwd()
    env_file = current_dir / ".env"
    
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Try to find .env in parent directories (up to 3 levels)
        for parent in list(current_dir.parents)[:3]:
            env_file = parent / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                break
except ImportError:
    # dotenv not installed, skip
    pass

__version__ = "0.1.0"
__author__ = "OpenMux Contributors"
__all__ = ["Orchestrator", "TaskType", "get_version"]


def __getattr__(name: str):
    """Lazy attribute loader for top-level exports.

    This avoids importing heavy dependencies (providers/aiohttp) at
    package import time while preserving the public API. Accessing
    Orchestrator or TaskType will import them on demand.
    """
    if name == "Orchestrator":
        from .core.orchestrator import Orchestrator as _Orch

        return _Orch
    if name == "TaskType":
        from .classifier.task_types import TaskType as _TT

        return _TT
    if name == "get_version":
        return get_version
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)


def get_version():
    """Get the current version of OpenMux."""
    return __version__
