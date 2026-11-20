#!/usr/bin/env python3
"""Joins, per run, what the Guardian decided with what actually left the machine.

For every ~/acs-434/run/<label>/ with a meta.json, inside that run's time window:
  - Guardian:  steps/toolCallRequest envelopes for WebFetch and the decision returned
  - Listener:  connections that reached the off-list listener (WPAD noise dropped)
  - Model:     the WebFetch tool_result Claude Code sent back to the (stub) model
Prints one row per run and writes summary.json next to the run directories.
"""
import json
import os
import sys

RUN = os.path.expanduser("~/acs-434/run")
AGT = os.path.expanduser("~/acs/reference-implementations/agt")


def jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def ts(rec):
    if "t" in rec:
        return rec["t"]
    from datetime import datetime
    return datetime.fromisoformat(rec["recorded_at"].replace("Z", "+00:00")).timestamp()


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], str):
            return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r:
                return r
    return None


def main(labels):
    envelopes = jsonl(os.path.join(AGT, ".acs/envelopes.jsonl"))
    listener = [r for r in jsonl(os.path.join(RUN, "listener.jsonl"))
                if "wpad" not in (r.get("host") or "") and r.get("bytes", 0) > 1]
    rows = []
    for label in labels:
        d = os.path.join(RUN, label)
        try:
            meta = json.loads(open(os.path.join(d, "meta.json")).read())
        except Exception as e:
            print(f"{label}: no meta ({e})")
            continue
        lo, hi = meta["start"], meta["end"]
        reqs = [e for e in envelopes if lo <= ts(e) <= hi and e.get("method") == "steps/toolCallRequest"]
        decisions = []
        for e in reqs:
            if e.get("direction") != "request":
                continue
            resp = next((r for r in reqs if r.get("direction") == "response" and r.get("rpc_id") == e.get("rpc_id")), None)
            decisions.append(find_key(resp, "decision") if resp else "(no response)")
        hits = [r for r in listener if lo <= r["t"] <= hi]
        tool_result, is_error = None, None
        for r in jsonl(os.path.join(d, "stub-requests.jsonl")):
            for m in r["body"].get("messages") or []:
                if m.get("role") == "user" and isinstance(m.get("content"), list):
                    for c in m["content"]:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            content = c.get("content")
                            text = content if isinstance(content, str) else json.dumps(content)
                            if "tool_reference" not in text:
                                tool_result, is_error = text, c.get("is_error", False)
        row = {
            "label": label, "url": meta["url"], "claude_exit": meta.get("claude_exit"),
            "guardian": decisions or ["(no WebFetch envelope)"],
            "listener_hits": [{k: h.get(k) for k in ("port", "proto", "sni", "host", "request_line")} for h in hits],
            "tool_result_is_error": is_error, "tool_result": (tool_result or "")[:600],
        }
        rows.append(row)
        reached = "; ".join(f"{h['port']}/{h['proto']} sni={h.get('sni')} host={h.get('host')}" for h in row["listener_hits"]) or "-"
        print(f"{label:22} guardian={','.join(map(str, row['guardian'])):8} listener={reached}")
        print(f"{'':22} model saw ({'error' if is_error else 'ok'}): {row['tool_result'][:220]!r}\n")
    json.dump(rows, open(os.path.join(RUN, "summary.json"), "w"), indent=2)


if __name__ == "__main__":
    labels = sys.argv[1:] or sorted(x for x in os.listdir(RUN) if os.path.exists(os.path.join(RUN, x, "meta.json")))
    main(labels)
