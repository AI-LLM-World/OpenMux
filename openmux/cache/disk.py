"""Disk-backed cache implementation.

Each cache entry is a JSON file under a base directory. This is simple and
works without external dependencies. Not optimized for high throughput.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from .base import BaseCache


class DiskCache(BaseCache):
    def __init__(self, base_path: Optional[str] = None):
        self.base = Path(base_path) if base_path else (Path.home() / ".openmux" / "cache")
        self.base.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.base / key

    async def get(self, key: str) -> Optional[str]:
        p = self._path_for(key)
        if not p.exists():
            return None
        try:
            with p.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            expiry = data.get("expiry", 0)
            if expiry != 0 and __import__("time").time() > expiry:
                try:
                    p.unlink()
                except Exception:
                    pass
                return None
            return data.get("value")
        except Exception:
            try:
                p.unlink()
            except Exception:
                pass
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        p = self._path_for(key)
        expiry = 0
        if ttl and ttl > 0:
            expiry = __import__("time").time() + int(ttl)
        tmp = p.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump({"expiry": expiry, "value": value}, fh)
            tmp.replace(p)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    async def invalidate(self, key: str) -> None:
        p = self._path_for(key)
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
