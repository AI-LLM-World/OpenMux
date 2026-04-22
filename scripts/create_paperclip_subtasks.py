#!/usr/bin/env python3
"""Create Paperclip subtasks for GSTA-70 when API creds are available.

This script reads the following environment variables:
- PAPERCLIP_API_URL
- PAPERCLIP_API_KEY
- PAPERCLIP_RUN_ID (optional)
- PAPERCLIP_COMPANY_ID
- PAPERCLIP_ISSUE_ID (optional, defaults to 'GSTA-70')

It will attempt to look up agents and create three subtasks (Staff, Release, QA).
If agents are not found it will create issues without assignees so they can be assigned later.

Run with: python scripts/create_paperclip_subtasks.py
"""

import os
import sys
import json
import urllib.request
import urllib.error


def get_env(name, required=False):
    v = os.getenv(name)
    if required and not v:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return v


API_URL = get_env("PAPERCLIP_API_URL", required=True).rstrip("/")
API_KEY = get_env("PAPERCLIP_API_KEY", required=True)
RUN_ID = get_env("PAPERCLIP_RUN_ID", required=False) or ""
COMPANY_ID = get_env("PAPERCLIP_COMPANY_ID", required=True)
PARENT_ISSUE = get_env("PAPERCLIP_ISSUE_ID", required=False) or "GSTA-70"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "X-Paperclip-Run-Id": RUN_ID,
    "Content-Type": "application/json",
}


def api_get(path):
    url = API_URL + path
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"GET {url} failed: {e}", file=sys.stderr)
        return None


def api_post(path, payload):
    url = API_URL + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        print(f"POST {url} failed: {e.code} {e.reason} - {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"POST {url} failed: {e}", file=sys.stderr)
        return None


def find_agents():
    data = api_get(f"/api/companies/{COMPANY_ID}/agents")
    if not data:
        return {}
    # data may be a list or a dict containing 'agents'
    agents = data if isinstance(data, list) else data.get("agents") or []
    m = {}
    for a in agents:
        key = a.get("urlKey") or a.get("url_key") or a.get("key")
        if key:
            m[key] = a.get("id") or a.get("agentId") or a.get("uuid")
    return m


def main():
    print("Looking up agents...")
    agents = find_agents()
    print("Agents found:", json.dumps(agents, indent=2))

    subtasks = [
        {
            "title": "Review: Add Redis cache tests and benchmark workflow",
            "description": "Review tests/unit/test_redis_cache.py, tests/benchmarks/test_cache_backends.py and .github/workflows/ci.yml changes. Verify style, test robustness, and that CI service configuration is correct.",
            "parentId": PARENT_ISSUE,
            "assigneeAgentId": agents.get("staff-engineer"),
            "status": "todo",
            "priority": "medium",
        },
        {
            "title": "CI Validation: Redis service and benchmark job",
            "description": "Run the CI pipeline for this branch, confirm redis service starts, unit tests pass, and benchmark job can be triggered manually. Investigate any service startup failures or permission issues.",
            "parentId": PARENT_ISSUE,
            "assigneeAgentId": agents.get("release-engineer"),
            "status": "todo",
            "priority": "medium",
        },
        {
            "title": "QA: Run and validate cache benchmarks",
            "description": "Run tests/benchmarks/test_cache_backends.py locally and in CI (manual trigger). Verify results, record baseline numbers, and file follow-ups if variance is high or results are unexpected.",
            "parentId": PARENT_ISSUE,
            "assigneeAgentId": agents.get("qa-engineer"),
            "status": "todo",
            "priority": "medium",
        },
    ]

    created = []
    for s in subtasks:
        payload = {k: v for k, v in s.items() if v is not None}
        print(f"Creating subtask: {payload['title']}")
        res = api_post(f"/api/companies/{COMPANY_ID}/issues", payload)
        if res:
            created.append(res)
            print("Created:", json.dumps(res, indent=2))
        else:
            print("Failed to create subtask:", payload['title'], file=sys.stderr)

    print(f"Created {len(created)} subtasks.")


if __name__ == "__main__":
    main()
