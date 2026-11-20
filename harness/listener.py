#!/usr/bin/env python3
"""Records every TCP connection that reaches it, and what the client sent first.

This is the "off-list host" for the run: if Claude Code's WebFetch connects
here, the egress gate let the request leave. It never answers TLS, so nothing
is served back; a connection attempt is the evidence.

For TLS it extracts the SNI from the ClientHello (the host name the client
believed it was talking to). For plain HTTP it records the request line and
Host header. One JSON line per connection goes to LISTENER_LOG.

usage: listener.py PORT [PORT ...]
"""
import json
import os
import socket
import sys
import threading
import time

LOG = os.environ.get("LISTENER_LOG", "listener.jsonl")
lock = threading.Lock()


def sni_from_client_hello(data):
    try:
        if len(data) < 5 or data[0] != 0x16:
            return None
        p = 5 + 4 + 2 + 32  # record hdr, handshake hdr, version, random
        p += 1 + data[p]  # session id
        p += 2 + int.from_bytes(data[p:p + 2], "big")  # cipher suites
        p += 1 + data[p]  # compression methods
        end = p + 2 + int.from_bytes(data[p:p + 2], "big")
        p += 2
        while p + 4 <= end:
            etype = int.from_bytes(data[p:p + 2], "big")
            elen = int.from_bytes(data[p + 2:p + 4], "big")
            if etype == 0:  # server_name
                q = p + 4 + 2
                nlen = int.from_bytes(data[q + 1:q + 3], "big")
                return data[q + 3:q + 3 + nlen].decode(errors="replace")
            p += 4 + elen
    except Exception:
        return None
    return None


def handle(conn, addr, port):
    conn.settimeout(3)
    data = b""
    try:
        data = conn.recv(4096)
    except Exception:
        pass
    finally:
        conn.close()
    rec = {"t": time.time(), "port": port, "peer": f"{addr[0]}:{addr[1]}", "bytes": len(data)}
    if data[:1] == b"\x16":
        rec["proto"] = "tls"
        rec["sni"] = sni_from_client_hello(data)
    else:
        rec["proto"] = "plain"
        head = data.split(b"\r\n\r\n", 1)[0].decode(errors="replace").split("\r\n")
        rec["request_line"] = head[0] if head else ""
        rec["host"] = next((h.split(":", 1)[1].strip() for h in head[1:] if h.lower().startswith("host:")), None)
    line = json.dumps(rec)
    with lock:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    print(line, flush=True)


def serve(port):
    s = socket.socket(socket.AF_INET6 if os.environ.get("LISTENER_V6") else socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(16)
    print(f"listening on 127.0.0.1:{port} -> {LOG}", flush=True)
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle, args=(conn, addr, port), daemon=True).start()


if __name__ == "__main__":
    ports = [int(p) for p in sys.argv[1:]] or [8443]
    for p in ports:
        threading.Thread(target=serve, args=(p,), daemon=True).start()
    while True:
        time.sleep(3600)
