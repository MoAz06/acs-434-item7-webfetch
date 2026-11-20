#!/usr/bin/env python3
"""Groups run/summary.json (written by analyse.py) by scenario across repetitions."""
import collections
import json
import os
import re

RUN = os.path.expanduser("~/acs-434/run")
rows = json.load(open(os.path.join(RUN, "summary.json")))
groups = collections.OrderedDict()
for r in rows:
    groups.setdefault(re.sub(r"-r\d+$", "", r["label"]), []).append(r)


def short(text):
    text = text or "(none)"
    if "hook error" in text:
        m = re.search(r"destination (\S+) not in allowlist", text)
        return f"hook deny: egress_destination_not_allowed ({m.group(1) if m else '?'})"
    if text.startswith("REDIRECT DETECTED"):
        m = re.search(r"Redirect URL[^:]*:\s*(\S+)", text)
        return f"redirect reported to model, not followed ({m.group(1) if m else '?'})"
    return text.strip().splitlines()[0][:90]


out = []
order = sorted(groups, key=lambda k: (k[0] != "c", k))
for name in order:
    rs = groups[name]
    dec = collections.Counter(d for r in rs for d in r["guardian"])
    res = collections.Counter(short(r["tool_result"]) for r in rs)
    hits = sum(len(r["listener_hits"]) for r in rs)
    exits = collections.Counter(r["claude_exit"] for r in rs)
    item = {"scenario": name, "url": rs[0]["url"], "reps": len(rs), "guardian": dict(dec),
            "host_outcome": dict(res), "listener_connections": hits, "claude_exit": dict(exits)}
    out.append(item)
    print(f"{name:24} n={len(rs)} guardian={dict(dec)} listener={hits} exit={dict(exits)}")
    for k, v in res.items():
        print(f"{'':24}   {v}x {k}")
json.dump(out, open(os.path.join(RUN, "aggregate.json"), "w"), indent=2)
