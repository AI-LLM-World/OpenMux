Title: feat(provider-registry): add entry-point plugin discovery and programmatic registration

Summary
-------
This change implements a dynamic provider plugin registry for OpenMux. It enables external packages to register providers via Python entry points (group `openmux.providers`) and also provides a programmatic registration API for runtime usage and tests.

Key changes
-----------
- openmux/providers/registry.py
  - Added entry-point discovery using importlib.metadata (with fallback to importlib_metadata if available).
  - Added `ProviderRegistry.register(provider: BaseProvider)` to allow runtime registration.
  - Discovery accepts provider instances, provider classes (instantiated without args), and zero-arg callables returning a provider.
  - Plugin providers override built-in providers by provider.name (lower-cased).
  - Discovery failures are logged and skipped (do not crash initialization).

- tests/unit/test_registry.py (new)
  - Unit tests that stub provider modules and entry points to validate discovery and programmatic registration behavior.

- docs/PROVIDER_PLUGINS.md (new)
  - Documentation describing how to author and publish plugins, discovery semantics, trust boundary, and examples.

- docs/TASK_LIST.md
  - Updated status for Task 2.3 (Provider Registry System) to reflect implemented parts and remaining items.

Why
---
Enables extensibility so third-party provider implementations can be integrated without modifying core OpenMux code. Useful for community plugins, enterprise provider wrappers, and test scaffolding.

Testing notes
-------------
1. Unit tests added to tests/unit/test_registry.py. They are isolated and stub provider submodules to avoid heavy optional deps.
2. Please run the full test suite in CI (pytest) to confirm compatibility with optional dependencies and integration tests.

Security/Trust
--------------
Entry point code executes at init time — this is a trust boundary. Plugin code can execute arbitrary Python during import/load. Recommend installing only trusted plugins and consider sandboxing/lazy-loading for future improvements.

Follow-ups
----------
- Add provider validation schema and automatic validation at registration (high priority).
- Add a debug CLI command `openmux providers --debug` to show discovered plugin origins, entry point names, and health.
- Consider lazy-loading or sandboxed discovery for security.

Reviewers
---------
- Staff Engineer (primary)
- Release Engineer (docs/release notes)
- QA Engineer (acceptance tests)

Checklist before merge
----------------------
- [ ] CI tests pass (unit + integration)
- [ ] Staff Engineer code review complete
- [ ] QA acceptance: test package plugin and override behavior
- [ ] Release notes updated
