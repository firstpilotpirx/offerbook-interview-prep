#!/usr/bin/env python3
"""Local server for the preparation page: serves dist/ and accepts marks from the page.

    run serve.py --dir ~/interview-prep            # start in background (or find one already running)
    run serve.py --dir ~/interview-prep --stop     # stop
    run serve.py --dir ~/interview-prep --foreground

Prints a line `PREP_URL http://localhost:<port>/` — the hub opens it in the built-in
browser and gives it to the person for their own browser.

API (localhost only):
    GET  /api/ping           {"ok":true,"dir":...}
    GET  /api/state          prep/page-state.json  (marks: done, skip, collapsed, startedAt)
    POST /api/state          write prep/page-state.json
    GET  /api/trainer        prep/trainer-state.json
    POST /api/trainer        write prep/trainer-state.json
    GET  /api/vocab          prep/vocab-state.json
    POST /api/vocab          write prep/vocab-state.json
    POST /api/inbox          append an "Interviews" form entry to prep/inbox.json
The page polls /version.json and reloads when the build changes.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8765
MAX_BODY = 2 * 1024 * 1024
DOCS = {"state": "page-state.json", "trainer": "trainer-state.json", "vocab": "vocab-state.json"}


def make_handler(root: Path):
    dist, prep = root / "dist", root / "prep"

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(dist), **kw)

        def log_message(self, *a):  # quiet
            pass

        extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                          ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
                          ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8"}

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _local(self):
            return self.client_address[0] in ("127.0.0.1", "::1", "localhost")

        def do_GET(self):
            p = self.path.split("?")[0]
            if p == "/api/ping":
                return self._json(200, {"ok": True, "dir": str(root)})
            if p.startswith("/api/") and p[5:] in DOCS:
                f = prep / DOCS[p[5:]]
                return self._json(200, json.loads(f.read_text(encoding="utf-8")) if f.exists() else {})
            return super().do_GET()

        def do_POST(self):
            if not self._local():
                return self._json(403, {"error": "local only"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._json(413, {"error": "too large"})
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "bad json"})
            p = self.path.split("?")[0]
            prep.mkdir(parents=True, exist_ok=True)
            if p.startswith("/api/") and p[5:] in DOCS:
                tmp = prep / (DOCS[p[5:]] + ".tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                tmp.replace(prep / DOCS[p[5:]])
                return self._json(200, {"ok": True})
            if p == "/api/inbox":
                f = prep / "inbox.json"
                items = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
                data["received"] = int(time.time() * 1000)
                items.append(data)
                f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
                return self._json(200, {"ok": True, "count": len(items)})
            return self._json(404, {"error": "unknown"})

    return H


def ping(port: int):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return json.loads(r.read())
    except Exception:
        return None


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    sys.exit("no free port")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--foreground", action="store_true")
    ap.add_argument("--stop", action="store_true")
    args = ap.parse_args()
    root = Path(args.dir).expanduser().resolve()
    pidfile = root / "prep" / ".serve.json"

    info = json.loads(pidfile.read_text()) if pidfile.exists() else {}
    if args.stop:
        if info.get("pid"):
            try:
                os.kill(info["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
        pidfile.unlink(missing_ok=True)
        print("stopped")
        return 0

    # already running for this folder?
    for port in [info.get("port"), args.port]:
        if port:
            r = ping(port)
            if r and r.get("dir") == str(root):
                print(f"PREP_URL http://localhost:{port}/")
                return 0

    (root / "dist").mkdir(parents=True, exist_ok=True)
    port = free_port(args.port)

    if args.foreground:
        srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root))
        pidfile.parent.mkdir(parents=True, exist_ok=True)
        pidfile.write_text(json.dumps({"pid": os.getpid(), "port": port}))
        print(f"PREP_URL http://localhost:{port}/", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    log = open(root / "dist" / ".serve.log", "a")
    proc = subprocess.Popen([sys.executable, __file__, "--dir", str(root), "--port", str(port), "--foreground"],
                            stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):
        if ping(port):
            print(f"PREP_URL http://localhost:{port}/")
            return 0
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    print("server did not start — see dist/.serve.log", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
