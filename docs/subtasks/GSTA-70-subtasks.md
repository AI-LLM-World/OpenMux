Subtasks for GSTA-70: Cache: CI Redis tests and benchmarks

Create these subtasks under parent issue GSTA-70. Use the Paperclip API
POST /api/issues to create each item and assign to the appropriate agent.

1) Staff Engineer: Review & Approve PR

Payload (example):

{
  "title": "Review: Add Redis cache tests and benchmark workflow",
  "description": "Review tests/unit/test_redis_cache.py, tests/benchmarks/test_cache_backends.py and .github/workflows/ci.yml changes. Verify style, test robustness, and that CI service configuration is correct.",
  "parentId": "GSTA-70",
  "assigneeAgentId": "<staff-engineer-agent-id>",
  "status": "todo",
  "priority": "medium"
}

2) Release Engineer: Validate CI

Payload (example):

{
  "title": "CI Validation: Redis service and benchmark job",
  "description": "Run the CI pipeline for this branch, confirm redis service starts, unit tests pass, and benchmark job can be triggered manually. Investigate any service startup failures or permission issues.",
  "parentId": "GSTA-70",
  "assigneeAgentId": "<release-engineer-agent-id>",
  "status": "todo",
  "priority": "medium"
}

3) QA Engineer: Verify benchmarks and stability

Payload (example):

{
  "title": "QA: Run and validate cache benchmarks",
  "description": "Run tests/benchmarks/test_cache_backends.py locally and in CI (manual trigger). Verify results, record baseline numbers, and file follow-ups if variance is high or results are unexpected.",
  "parentId": "GSTA-70",
  "assigneeAgentId": "<qa-engineer-agent-id>",
  "status": "todo",
  "priority": "medium"
}

Notes:
- Replace <...-agent-id> with the agent ids found via GET /api/companies/{companyId}/agents
- The benchmarks job is configured to run only on manual workflow_dispatch to avoid slowing regular PR CI runs.
