#!/usr/bin/env python3
"""herdr-valet web page (valet.py): see what was open, resume, delete a card or park an open
session.

One process per person, under their own user (install.sh sets it up as a user service): it only
sees that person's herdr and cards. Listens on 127.0.0.1 (port from the config; default 8790 +
(uid - 1000)). To reach it from another device, put an authenticating proxy in front: the page
resumes and closes sessions. No dependencies: standard library only.

Resuming from here opens a herdr workspace with the resume command running inside: the
conversation is ready in the terminal, which is where the work happens.
"""

from __future__ import annotations


import json
from datetime import datetime
import os
import pwd
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import valet  # noqa: E402

USER = pwd.getpwuid(os.getuid()).pw_name
PORT = int(os.environ.get("HERDR_VALET_PORT") or valet.CONF["port"])
SESSION_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PANE_RE = re.compile(r"^w[0-9A-Za-z]+:p[0-9A-Za-z]+$")
PAGE = Path(__file__).resolve().parent / "web.html"
# Only requests with a loopback Host are served. Without this, DNS rebinding lets a page from
# another site become "same origin" with this one, read the summaries and send actions with
# X-Parking. A proxy in front (nginx with proxy_pass to 127.0.0.1) sends this Host by default.
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}"}


def state() -> dict:
    try:
        live, herdr_error = valet.live_sessions(), None
    except Exception as e:  # noqa: BLE001 — without herdr the page still shows the cards
        live, herdr_error = [], str(e)
    history = []
    if valet.HISTORY.is_dir():
        # resumed_at comes from the card; cards moved before it was recorded fall back to the
        # file's mtime, which is the park time (a rename keeps it).
        rows = []
        for p in valet.HISTORY.glob("*.json"):
            c = json.loads(p.read_text())
            at = c.get("resumed_at")
            c["resumed_at"] = datetime.fromisoformat(at).timestamp() if at else p.stat().st_mtime
            rows.append(c)
        history = sorted(rows, key=lambda c: c["resumed_at"], reverse=True)[:15]
    return {
        "user": USER,
        "idle_days": valet.CONF["idle_days"],
        "herdr_running": valet.herdr_running(),
        "parked": valet.cards(),
        "live": live,
        "history": history,
        "herdr_error": herdr_error,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "herdr-valet"

    def log_message(self, fmt, *args):  # noqa: N802 — no journal noise for every GET
        pass

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

    def _host_ok(self) -> bool:
        if self.headers.get("Host", "") in ALLOWED_HOSTS:
            return True
        self._json(HTTPStatus.MISDIRECTED_REQUEST, {"error": "Host not allowed"})
        return False

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/state":
            self._json(200, state())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if not self._host_ok():
            return
        # A form on another page cannot send this header without a preflight (and none is
        # allowed): actions only come from this page.
        if self.headers.get("X-Parking") != "1":
            self._json(HTTPStatus.FORBIDDEN, {"error": "missing X-Parking"})
            return
        m = re.fullmatch(r"/api/(resume|delete|park)/([^/]+)", self.path)
        if not m:
            self._json(404, {"error": "not found"})
            return
        action, target = m.groups()
        try:
            if action == "park":
                if not PANE_RE.match(target):
                    raise ValueError("invalid pane")
                card = valet.park(target, "manual")
                self._json(200, {"ok": True, "card": card})
                return
            if not SESSION_RE.match(target) or not valet.card_path(target).exists():
                raise ValueError("no card for that session")
            if action == "delete":
                valet.card_path(target).unlink()
                valet.log(f"deleted {target} (web)")
                self._json(200, {"ok": True})
            else:
                ws = valet.resume_in_herdr(target)
                self._json(200, {"ok": True, "workspace": ws})
        except valet.HerdrDown as e:
            self._json(
                HTTPStatus.CONFLICT,
                {
                    "error": "herdr is not running: open the terminal (herdr) and press Resume again, "
                    "or run this command in any terminal",
                    "command": str(e),
                },
            )
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": f"{e.__class__.__name__}: {e}"})


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"herdr-valet de {USER} en http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
