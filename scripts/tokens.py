#!/usr/bin/env python3
"""Print token usage from a Devin --export conversation."""
import json
import sys

path = sys.argv[1]
with open(path) as fh:
    data = json.load(fh)

metrics = data.get("final_metrics") or {}
prompt = int(metrics.get("total_prompt_tokens", 0))
completion = int(metrics.get("total_completion_tokens", 0))
cached = int(metrics.get("total_cached_tokens", 0))

print(json.dumps({
    "prompt": prompt,
    "completion": completion,
    "cached": cached,
    "total": prompt + completion,
    "billable": max(0, prompt - cached) + completion,
}))
