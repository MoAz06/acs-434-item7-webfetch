#!/usr/bin/env python3
"""Stub for Anthropic's /v1/messages, so Claude Code runs with a scripted model.

Only the model is faked. Claude Code, the ACS hook shim and the Guardian are real.

Behaviour, per request:
  - the conversation's last user turn carries a tool_result  -> reply with text, end_turn
  - the request offers a WebFetch tool and has no tool_result -> reply with ONE WebFetch tool_use
  - anything else (WebFetch's own content-processing call, titles, ...) -> reply with short text

The URL to fetch comes from STUB_FETCH_URL. Every request body is appended to
STUB_LOG (JSONL), so the report can show exactly what reached the "model",
including the tool_result Claude Code echoed back.
"""
import json
import os
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("STUB_PORT", "9100"))
FETCH_URL = os.environ.get("STUB_FETCH_URL", "https://docs.anthropic.com/en/docs")
LOG = os.environ.get("STUB_LOG", "stub-requests.jsonl")


def last_user_has_tool_result(body):
    msgs = body.get("messages") or []
    for m in reversed(msgs):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, list):
            return any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)
        return False
    return False


def offers_webfetch(body):
    return any((t or {}).get("name") == "WebFetch" for t in body.get("tools") or [])


def called_tools(body):
    names = []
    for m in body.get("messages") or []:
        if m.get("role") == "assistant" and isinstance(m.get("content"), list):
            names += [c.get("name") for c in m["content"] if isinstance(c, dict) and c.get("type") == "tool_use"]
    return names


def offers(body, name):
    return any((t or {}).get("name") == name for t in body.get("tools") or [])


def plan(body):
    # WebFetch is a deferred tool in recent Claude Code: load it with ToolSearch first.
    if not body.get("tools"):
        return ("text", "stub reply")  # WebFetch's own content-processing call, titles, ...
    called = called_tools(body)
    if "WebFetch" in called:
        return ("text", "Done.")
    if offers(body, "WebFetch") or "ToolSearch" in called:
        return ("tool_use", ("WebFetch", {"url": FETCH_URL, "prompt": "Return the page text verbatim."}))
    if offers(body, "ToolSearch"):
        return ("tool_use", ("ToolSearch", {"query": "select:WebFetch", "max_results": 1}))
    return ("text", "stub reply")


def sse(handler, event, data):
    handler.wfile.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())
    handler.wfile.flush()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[stub] " + (fmt % args) + "\n")

    def _json(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._json(200, {"ok": True})

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("content-length", "0")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        path = self.path.split("?")[0]
        kind, value = plan(body) if path.endswith("/v1/messages") else ("other", None)
        with open(LOG, "a") as f:
            f.write(json.dumps({"t": time.time(), "path": self.path, "reply": kind, "body": body}) + "\n")

        if path.endswith("/count_tokens"):
            return self._json(200, {"input_tokens": 10})
        if not path.endswith("/v1/messages"):
            return self._json(200, {})

        model = body.get("model", "stub")
        msg_id = "msg_" + uuid.uuid4().hex[:24]
        usage = {"input_tokens": 10, "output_tokens": 5}
        if kind == "tool_use":
            tool_name, value = value
            block = {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:24], "name": tool_name, "input": value}
            stop = "tool_use"
        else:
            block = {"type": "text", "text": value}
            stop = "end_turn"

        if not body.get("stream"):
            return self._json(200, {"id": msg_id, "type": "message", "role": "assistant", "model": model,
                                    "content": [block], "stop_reason": stop, "stop_sequence": None, "usage": usage})

        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        sse(self, "message_start", {"type": "message_start", "message": {
            "id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}})
        if kind == "tool_use":
            sse(self, "content_block_start", {"type": "content_block_start", "index": 0,
                                              "content_block": {**block, "input": {}}})
            sse(self, "content_block_delta", {"type": "content_block_delta", "index": 0,
                                              "delta": {"type": "input_json_delta", "partial_json": json.dumps(value)}})
        else:
            sse(self, "content_block_start", {"type": "content_block_start", "index": 0,
                                              "content_block": {"type": "text", "text": ""}})
            sse(self, "content_block_delta", {"type": "content_block_delta", "index": 0,
                                              "delta": {"type": "text_delta", "text": value}})
        sse(self, "content_block_stop", {"type": "content_block_stop", "index": 0})
        sse(self, "message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                    "usage": {"output_tokens": 5}})
        sse(self, "message_stop", {"type": "message_stop"})
        self.close_connection = True


if __name__ == "__main__":
    print(f"stub model on 127.0.0.1:{PORT}, fetch url {FETCH_URL!r}, log {LOG}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
