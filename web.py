#!/usr/bin/env python3
"""Página web de herdr-valet (valet.py): ver qué había abierto, reanudar, borrar la ficha o
aparcar una sesión abierta.

Un proceso por persona, con su usuario (lo instala install.sh como servicio de usuario): solo ve
su herdr y sus fichas. Escucha en 127.0.0.1 (puerto en la config; por defecto 8790 + (uid -
1000)). Para verla desde otro dispositivo, ponerle adelante un proxy con autenticación: la
página reanuda y cierra sesiones. Sin dependencias: biblioteca estándar.

Reanudar desde acá abre un workspace en herdr con el comando de reanudación corriendo adentro:
la conversación queda lista en la terminal, que es donde se trabaja.
"""

from __future__ import annotations


import json
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
# Solo se atiende con el Host de loopback. Sin esto, DNS rebinding deja que una página de otro
# sitio se vuelva "mismo origen" con esta y lea los resúmenes o mande acciones con X-Parking.
# Un proxy delante (nginx con proxy_pass a 127.0.0.1) manda este Host por defecto.
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}"}


def state() -> dict:
    try:
        live, herdr_error = valet.live_sessions(), None
    except Exception as e:  # noqa: BLE001 — sin herdr la página igual muestra las fichas
        live, herdr_error = [], str(e)
    history = []
    if valet.HISTORY.is_dir():
        files = sorted(valet.HISTORY.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        history = [{**json.loads(p.read_text()), "resumed_at": p.stat().st_mtime} for p in files[:15]]
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

    def log_message(self, fmt, *args):  # noqa: N802 — sin ruido en el journal por cada GET
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
        self._json(HTTPStatus.MISDIRECTED_REQUEST, {"error": "Host no permitido"})
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
            self._json(404, {"error": "no existe"})

    def do_POST(self):  # noqa: N802
        if not self._host_ok():
            return
        # Un formulario de otra página no puede mandar este header sin preflight (y no se
        # permite ninguno): las acciones solo salen de esta página.
        if self.headers.get("X-Parking") != "1":
            self._json(HTTPStatus.FORBIDDEN, {"error": "falta X-Parking"})
            return
        m = re.fullmatch(r"/api/(resume|delete|park)/([^/]+)", self.path)
        if not m:
            self._json(404, {"error": "no existe"})
            return
        action, target = m.groups()
        try:
            if action == "park":
                if not PANE_RE.match(target):
                    raise ValueError("panel inválido")
                card = valet.park(target, "manual")
                self._json(200, {"ok": True, "card": card})
                return
            if not SESSION_RE.match(target) or not valet.card_path(target).exists():
                raise ValueError("no hay ficha para esa sesión")
            if action == "delete":
                valet.card_path(target).unlink()
                valet.log(f"borrada {target} (web)")
                self._json(200, {"ok": True})
            else:
                ws = valet.resume_in_herdr(target)
                self._json(200, {"ok": True, "workspace": ws})
        except valet.HerdrDown as e:
            self._json(
                HTTPStatus.CONFLICT,
                {
                    "error": "herdr no está corriendo: abre la terminal (herdr) y vuelve a tocar "
                    "Reanudar, o corre este comando en cualquier terminal",
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
