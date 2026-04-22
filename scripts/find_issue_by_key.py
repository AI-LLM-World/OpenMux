#!/usr/bin/env python3
"""Find a Paperclip issue by key (e.g. GSTA-70) and print its UUID.

Usage: set PAPERCLIP_API_URL, PAPERCLIP_API_KEY, PAPERCLIP_COMPANY_ID, then run.
"""
import os
import sys
import json
import urllib.request

API_URL = os.getenv("PAPERCLIP_API_URL")
API_KEY = os.getenv("PAPERCLIP_API_KEY")
COMPANY_ID = os.getenv("PAPERCLIP_COMPANY_ID")
KEY = os.getenv("PAPERCLIP_ISSUE_ID_KEY", "GSTA-70")

if not API_URL or not API_KEY or not COMPANY_ID:
    print("Please set PAPERCLIP_API_URL, PAPERCLIP_API_KEY, and PAPERCLIP_COMPANY_ID", file=sys.stderr)
    sys.exit(1)

API_URL = API_URL.rstrip("/")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "X-Paperclip-Run-Id": os.getenv("PAPERCLIP_RUN_ID", "")}

def api_get(path):
    req = urllib.request.Request(API_URL + path, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)

def main():
    issues = api_get(f"/api/companies/{COMPANY_ID}/issues")
    # issues may be a dict containing 'items' or a list
    items = []
    if isinstance(issues, dict):
        items = issues.get("items") or issues.get("issues") or []
    elif isinstance(issues, list):
        items = issues

    found = []
    for it in items:
        # try several keys
        if any(KEY in str(it.get(k, "")) for k in ("id", "title", "key", "externalId")):
            found.append(it)

    if not found:
        print("No matching issues found for key=", KEY)
        # print short listing
        print(f"Total issues fetched: {len(items)}")
        return

    print(json.dumps(found, indent=2))

if __name__ == '__main__':
    main()
