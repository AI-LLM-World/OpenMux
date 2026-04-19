# Provider Plugins (openmux.providers)

Status: Implemented (entry-point discovery) — in review

Overview
--------
OpenMux now supports a plugin-based provider registry using Python entry points. External packages can expose provider implementations under the entry point group "openmux.providers". These are discovered at ProviderRegistry initialization and registered automatically.

Goals
-----
- Allow third-party providers to integrate without modifying the OpenMux core.
- Keep built-in providers as safe fallbacks for users who don't install plugins.
- Make plugin discovery robust and safe: failures in plugin loading should not crash the main package.

Discovery semantics
-------------------
- Group: openmux.providers
- Acceptable entry point returns:
  - A BaseProvider instance
  - A BaseProvider subclass (instantiated with no args)
  - A zero-arg callable that returns a BaseProvider instance
- If multiple providers register the same provider.name (case-insensitive), the plugin provider will replace any built-in registration.
- Failures (exceptions during load/instantiation/call) are logged and the entry point is skipped.

Trust boundary
--------------
Entry point code is executed at init time. This means plugins can execute arbitrary Python code during their import/load. Only install plugins from trusted sources in production environments. Consider these mitigations:

- Use virtual environments for isolation
- Audit provider packages before deployment
- In future: consider lazy-loading plugins or running discovery in a sandboxed process

How to publish a provider plugin
--------------------------------
Example provider implementation (minimal):

```python
from openmux.providers.base import BaseProvider

class MyCoolProvider(BaseProvider):
    def __init__(self):
        super().__init__("MyCool")

    def is_available(self):
        return True

    def supports_task(self, task_type):
        # Implement capability checks
        return True

    async def generate(self, prompt: str, **kwargs) -> str:
        return "mycool response"

```

Package metadata (pyproject.toml) example:

```toml
[project.entry-points."openmux.providers"]
mycool = "mycool.providers:MyCoolProvider"
```

Alternative (setuptools in setup.cfg):

```
[options.entry_points]
openmux.providers =
    mycool = mycool.providers:MyCoolProvider
```

Programmatic registration
-------------------------
You can also register providers at runtime:

```python
from openmux.providers.registry import ProviderRegistry
from mycool.providers import MyCoolProvider

registry = ProviderRegistry()
registry.register(MyCoolProvider())
```

Testing plugins locally
-----------------------
1. Build and install your plugin package into a virtualenv: `pip install -e .`
2. Verify discovery by importing openmux and inspecting ProviderRegistry:

```python
from openmux.providers.registry import ProviderRegistry
reg = ProviderRegistry()
print(reg.get_all().keys())
```

Notes and future work
---------------------
- Provider validation (JSON schema for capabilities) is planned and partially in progress.
- Hot-reload support for dynamic provider changes is a low-priority improvement.
- Consider adding an admin/debug CLI command `openmux providers --debug` to show plugin origins and health.

Files changed / tests
---------------------
- Modified: openmux/providers/registry.py (entry-point discovery, register API)
- Added: tests/unit/test_registry.py (unit tests that stub provider modules and entry points)
- Updated: docs/TASK_LIST.md (status update)

If you want, I will:
- Draft a PR and assign to Staff Engineer for review
- Add provider validation schema and matching tests
- Implement a debug CLI for plugin inspection

Which of the above should I prioritize next?
