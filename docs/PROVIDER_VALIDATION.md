Provider Validation Design (follow-up for GSTA-60)
===============================================

Status: Draft design. This work is a follow-up to the provider plugin registry implementation. The implementation of runtime enforcement will be delivered in a separate PR after the main plugin-registry PR is opened.

Goals
-----
- Provide a small, deterministic validation layer to ensure registered providers conform to the BaseProvider contract and expose expected attributes.
- Avoid new runtime dependencies in the short term. Keep runtime checks lightweight and defensive.
- Provide an optional stronger validation path (JSON Schema + jsonschema) for users who opt-in.

Principles
----------
- Fail fast for clearly invalid providers (e.g., missing name, generate not callable) during programmatic registration.
- Do not crash the entire discovery process if a plugin fails validation: skip the plugin and log a clear warning with diagnostics.
- Keep default validation conservative to avoid rejecting valid but unusual provider implementations.

Validation target shape
-----------------------
Minimum requirements for a provider instance (checked at register time):

1. provider.name: non-empty string
2. provider.is_available: callable
3. provider.supports_task: callable
4. provider.generate: coroutine function or callable that returns a coroutine when called (i.e., asyncio.iscoroutinefunction or inspect.isawaitable when called)
5. Optional: provider.health (ProviderHealth instance) or health_check coroutine method

Optional capability metadata (recommended for richer validation):
- provider.capabilities: dict with keys like "tasks": ["chat","code","embedding"], "models": ["model-id-1"]

JSON Schema (optional advanced validation)
-----------------------------------------
Example JSON Schema (for capability metadata, not used by default):

{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OpenMux Provider Capabilities",
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "tasks": {"type": "array", "items": {"type": "string"}},
    "models": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["name", "tasks"]
}

Runtime enforcement strategy
----------------------------
Short term (no new deps):

- Implement a small validator utility used by ProviderRegistry.register() and entry-point discovery logic.
- Checks listed in Validation target shape.
- When provider.generate is checked, we will not call it (to avoid side-effects). Instead, ensure it's an async callable (inspect.iscoroutinefunction) or a callable that returns an awaitable when invoked with a harmless short-circuit input (risky). We will prefer inspect checks.

Long term (opt-in strong validation):

- Add optional dependency on `jsonschema` and validate provider.capabilities if present.
- Provide a CLI flag or environment variable to enforce strict validation: `OPENMUX_STRICT_PROVIDER_VALIDATION=1`.

Error reporting & telemetry
---------------------------
- Log structured warnings when validation fails: include provider entry-point name (if available), exception trace, and which validation rule failed.
- Emit a metric (if metrics system available) for plugin_validation_failures with labels (rule, package)

Unit tests to add
-----------------
1. test_register_invalid_provider_raises: programmatic registration of an invalid object (missing name or missing methods) should raise TypeError in register().
2. test_entry_point_invalid_provider_skipped: entry-point that returns invalid object should be skipped and logged; registry continues.
3. test_generate_must_be_async_or_awaitable: ensure providers with sync-only generate are rejected.

Backward compatibility considerations
-----------------------------------
- Many provider implementations already exist in this repo (OpenRouter, HuggingFace, Ollama, Mistral, Together). Ensure the validator passes these by testing them in CI.
- Validator must be permissive enough to accept provider.generate that is an async function or an object implementing __call__ that is awaitable.

Implementation checklist (small incremental PR)
---------------------------------------------
- [ ] Add validator util: openmux/providers/validator.py
- [ ] Wire validator into ProviderRegistry.register() and entry-point discovery flow (call validate_provider(provider, source_info))
- [ ] Add tests (tests/unit/test_registry_validation.py or extend tests/unit/test_registry.py)
- [ ] Add a note in docs/PROVIDER_PLUGINS.md about validation and strict mode.

Timeline
--------
- Design & tests: 1 day (done: design)
- Implementation & unit tests: 1 day
- QA/CI validation against built-in providers: 0.5 day

If you want, I'll create the validator utility and tests now on a new branch (feat/gsta-60-provider-validation) and open a PR after the plugin-registry PR is created. Confirm if I should proceed.
