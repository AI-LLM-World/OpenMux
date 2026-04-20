PR Review & Acceptance Checklist (for feat/gsta-60-provider-registry)

Assign:
- Staff Engineer: @staff-engineer
- Release Engineer: @release-engineer
- QA Engineer: @qa-engineer

Review tasks (Staff Engineer)
- [ ] Review openmux/providers/registry.py for importlib.metadata usage and Python-version compatibility.
- [ ] Confirm discovery precedence (plugin overrides built-ins) is acceptable.
- [ ] Validate logging and error handling semantics during discovery.

Docs & Release (Release Engineer)
- [ ] Review docs/PROVIDER_PLUGINS.md for clarity and packaging examples.
- [ ] Add a short release note summarising plugin discovery and the trust boundary.

QA Acceptance (QA Engineer)
- [ ] Create a tiny plugin package locally exposing an entry point `openmux.providers = mycool = mycool.providers:MyCoolProvider` and verify discovery after `pip install -e .`.
- [ ] Verify built-in override: plugin registers provider with the same `name` as a built-in (e.g., OpenRouter) and confirm plugin is used instead of built-in.
- [ ] Run integration tests that exercise orchestrator selection/routing to a plugin provider (if possible).

Follow-ups (Owner: CTO)
- [ ] Implement provider validation schema and enforce at registration time.
- [ ] Add `openmux providers --debug` CLI to show provider origin, entry point, and health.
