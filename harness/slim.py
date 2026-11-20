#!/usr/bin/env python3
"""Writes model-saw.jsonl next to each stub-requests.jsonl.

The full request log carries Claude Code's whole system prompt, tool schemas and local
paths, none of which is evidence. This keeps, per request: the path, what the stub
replied, which tool names were offered, and every tool_use / tool_result in the
conversation. That is enough to show what the model was offered and what came back.
"""
import glob
import json
import os

for src in glob.glob(os.path.expanduser("~/acs-434/*/*/stub-requests.jsonl")):
    out = []
    for line in open(src):
        r = json.loads(line)
        b = r.get("body") or {}
        blocks = []
        for m in b.get("messages") or []:
            if isinstance(m.get("content"), list):
                for c in m["content"]:
                    if isinstance(c, dict) and c.get("type") in ("tool_use", "tool_result"):
                        c = {k: v for k, v in c.items() if k != "cache_control"}
                        blocks.append({"role": m.get("role"), **c})
        out.append({"t": r.get("t"), "path": r.get("path"), "stub_reply": r.get("reply"),
                    "model": b.get("model"),
                    "tools_offered": [t.get("name") for t in b.get("tools") or []],
                    "tool_blocks": blocks})
    with open(os.path.join(os.path.dirname(src), "model-saw.jsonl"), "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
print("slimmed", len(glob.glob(os.path.expanduser("~/acs-434/*/*/model-saw.jsonl"))), "runs")
