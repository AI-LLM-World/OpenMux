# Unit tests for ProviderRegistry (plugin discovery and programmatic registration)
import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = ROOT / "openmux" / "providers"
BASE_PATH = str(PROVIDERS_DIR / "base.py")
REGISTRY_PATH = str(PROVIDERS_DIR / "registry.py")


class _FakeEntryPoint:
    def __init__(self, name, obj):
        self.name = name
        self._obj = obj

    def load(self):
        return self._obj


class _FakeEntryPoints:
    def __init__(self, eps):
        self._eps = eps

    def select(self, group=None):
        return self._eps


class _FakeMetadata:
    def __init__(self, eps):
        self._eps = eps

    def entry_points(self):
        return _FakeEntryPoints(self._eps)


def _make_stub_provider_class(base_cls, provider_name):
    """Create a simple BaseProvider subclass for tests."""

    class_name = provider_name.capitalize() + "Provider"

    def _init(self):
        base_cls.__init__(self, provider_name.capitalize())

    def _is_available(self):
        return True

    def _supports_task(self, task_type):
        return True

    async def _generate(self, prompt, **kwargs):
        return f"{provider_name}-resp"

    attrs = {
        "__init__": _init,
        "is_available": _is_available,
        "supports_task": _supports_task,
        "generate": _generate,
    }

    return type(class_name, (base_cls,), attrs)


def _load_registry_module_with_stubs():
    """Load the registry module while stubbing provider submodules.

    Returns the loaded registry module and the loaded base module.
    """
    # Ensure a clean environment for these module names
    keys_to_remove = [
        "openmux.providers",
        "openmux.providers.base",
        "openmux.providers.openrouter",
        "openmux.providers.huggingface",
        "openmux.providers.ollama",
        "openmux.providers.mistral",
        "openmux.providers.together",
        "openmux.providers.registry",
    ]
    for k in keys_to_remove:
        if k in sys.modules:
            sys.modules.pop(k)

    # Create a dummy package module for openmux.providers to avoid
    # executing the real package __init__.py during imports.
    pkg = types.ModuleType("openmux.providers")
    pkg.__path__ = [str(PROVIDERS_DIR.resolve())]
    sys.modules["openmux.providers"] = pkg

    # Load base.py into sys.modules under openmux.providers.base
    spec_base = importlib.util.spec_from_file_location(
        "openmux.providers.base", BASE_PATH
    )
    base_mod = importlib.util.module_from_spec(spec_base)
    sys.modules["openmux.providers.base"] = base_mod
    spec_base.loader.exec_module(base_mod)

    BaseProvider = base_mod.BaseProvider

    # Create stub provider modules for built-ins
    for name in [
        "openrouter",
        "huggingface",
        "ollama",
        "mistral",
        "together",
    ]:
        module_name = f"openmux.providers.{name}"
        mod = types.ModuleType(module_name)
        provider_cls = _make_stub_provider_class(BaseProvider, name)
        # Attach with the expected exported class name
        exported_name = (
            "HuggingFaceProvider" if name == "huggingface" else name.capitalize() + "Provider"
        )
        setattr(mod, exported_name, provider_cls)
        sys.modules[module_name] = mod

    # Load registry module directly (avoids importing openmux.providers.__init__)
    spec_reg = importlib.util.spec_from_file_location("openmux.providers.registry", REGISTRY_PATH)
    reg_mod = importlib.util.module_from_spec(spec_reg)
    sys.modules["openmux.providers.registry"] = reg_mod
    spec_reg.loader.exec_module(reg_mod)

    return reg_mod, base_mod


def _cleanup_modules():
    for k in list(sys.modules.keys()):
        if k.startswith("openmux.providers"):
            sys.modules.pop(k, None)


def test_register_programmatically_and_overwrite():
    reg_mod, base_mod = _load_registry_module_with_stubs()
    try:
        # Disable entry point discovery for determinism
        reg_mod._importlib_metadata = None

        registry = reg_mod.ProviderRegistry()

        # Programmatic registration
        BaseProvider = base_mod.BaseProvider

        class CustomProvider(BaseProvider):
            def __init__(self):
                super().__init__("Custom")

            def is_available(self):
                return True

            def supports_task(self, task_type):
                return True

            async def generate(self, prompt, **kwargs):
                return "ok"

        cp = CustomProvider()
        registry.register(cp)

        assert registry.get("custom") is cp

        # Overwrite existing provider with same name
        cp2 = CustomProvider()
        registry.register(cp2)
        assert registry.get("custom") is cp2

        # Invalid registration should raise
        with pytest.raises(TypeError):
            registry.register(object())

    finally:
        _cleanup_modules()


def test_entry_point_class_and_callable_registration():
    reg_mod, base_mod = _load_registry_module_with_stubs()
    try:
        BaseProvider = base_mod.BaseProvider

        # Plugin that exposes a provider class
        class PluginClass(BaseProvider):
            def __init__(self):
                super().__init__("PluginClass")

            def is_available(self):
                return True

            def supports_task(self, task_type):
                return True

            async def generate(self, prompt, **kwargs):
                return "pc"

        # Plugin that exposes a factory callable returning an instance
        class PluginFactoryClass(BaseProvider):
            def __init__(self):
                super().__init__("PluginFactory")

            def is_available(self):
                return True

            def supports_task(self, task_type):
                return True

            async def generate(self, prompt, **kwargs):
                return "pf"

        def factory():
            return PluginFactoryClass()

        eps = [
            _FakeEntryPoint("pc", PluginClass),
            _FakeEntryPoint("pf", factory),
        ]

        reg_mod._importlib_metadata = _FakeMetadata(eps)

        registry = reg_mod.ProviderRegistry()

        # Plugin names become keys (lower-cased provider.name)
        assert registry.get("pluginclass") is not None
        assert registry.get("pluginfactory") is not None

    finally:
        _cleanup_modules()


def test_entry_point_callable_with_args_skipped_and_override_builtin():
    reg_mod, base_mod = _load_registry_module_with_stubs()
    try:
        BaseProvider = base_mod.BaseProvider

        # Callable that requires args -> should be skipped
        def bad_factory(x):
            return None

        # Callable that provides an overriding OpenRouter provider
        class OpenRouterOverride(BaseProvider):
            def __init__(self):
                super().__init__("OpenRouter")

            def is_available(self):
                return True

            def supports_task(self, task_type):
                return True

            async def generate(self, prompt, **kwargs):
                return "overridden"

        eps = [
            _FakeEntryPoint("bad", bad_factory),
            _FakeEntryPoint("openrouter_override", OpenRouterOverride),
        ]

        reg_mod._importlib_metadata = _FakeMetadata(eps)

        registry = reg_mod.ProviderRegistry()

        # bad factory should not be registered
        assert registry.get("bad") is None

        # override should replace the built-in openrouter
        p = registry.get("openrouter")
        assert p is not None
        assert p.name.lower() == "openrouter"

    finally:
        _cleanup_modules()
