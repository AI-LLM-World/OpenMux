Follow-up task: Provider Validation (GSTA-60)

Owner: CTO
Priority: high
Estimate: 1-2 days

Description:
- Implement a lightweight validation util for provider instances and integrate it into ProviderRegistry.register() and entry-point discovery.
- Add unit tests to ensure invalid providers are rejected or skipped and that built-in providers pass validation.

Acceptance criteria:
- Validator implemented and covered by unit tests.
- ProviderRegistry calls validator during discovery and programmatic registration.
- No regressions in existing unit tests.

Next steps:
1. Create feature branch feat/gsta-60-provider-validation
2. Implement validator and tests
3. Open PR and assign Staff Engineer
