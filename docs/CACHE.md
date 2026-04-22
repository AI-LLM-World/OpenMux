Cache subsystem
================

This document describes the response caching subsystem and how to configure it.

Configuration (config/default_config.json)

Example snippet:

{
  "cache": {
    "enabled": false,
    "backend": "memory",   # one of: memory, disk, redis
    "ttl": 3600,
    "path": null            # disk path or redis URL for redis backend
  }
}

Backends
- memory: in-process memory cache (fast, ephemeral)
- disk: simple JSON-file-backed cache under the configured path
- redis: uses redis.asyncio and requires redis to be reachable

Notes
- If redis backend is configured but redis is not available, initialization
  will fail and the orchestrator will disable caching for safety (a warning
  will be logged).
- Cache keys are SHA256(json.dumps(payload, sort_keys=True)) — the payload
  currently includes the query and task type. Be careful to include any
  request-specific parameters (temperature, system_prompt, session_id) if
  you want them to be part of the cache key.

Metrics
- cache_hit
- cache_miss
- cache_set
- cache_error
