"""Minimal local relay + overlay server for Doomguy face rendering.

Run:
    python examples/local_overlay_server.py

Then in OBS Browser Source (OVERLAY_FACE_OUTPUT), set URL to:
    http://127.0.0.1:8765/overlay

Send health samples to:
    POST http://127.0.0.1:8765/v1/health-sample
"""

from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from doomguy_overlay_engine import DoomguyFaceEngine
HOST = "127.0.0.1"
PORT = 8765

engine = DoomguyFaceEngine()
state_lock = threading.Lock()
latest = {
    "frame": "STFST01",
    "health_percent": 100,
    "health_bucket": 0,
    "look": "center",
    "is_pain": False,
    "updated_at_ms": int(time.time() * 1000),
}

OVERLAY_HTML = """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Doomguy Overlay</title>
    <style>
      html, body {
        margin: 0;
        background: transparent;
        overflow: hidden;
      }
      #face {
        image-rendering: pixelated;
        image-rendering: crisp-edges;
        width: 100%;
        height: auto;
        display: block;
      }
    </style>
  </head>
  <body>
    <img id=\"face\" src=\"/STFST01.png\" alt=\"doomguy\" />
    <script>
      const img = document.getElementById('face');
      let last = 'STFST01';
      async function tick() {
        const r = await fetch('/v1/face-state', { cache: 'no-store' });
        const s = await r.json();
        if (s.frame && s.frame !== last) {
          last = s.frame;
          img.src = '/' + s.frame + '.png';
        }
      }
      setInterval(tick, 100);
      tick();
    </script>
  </body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/overlay":
            self._send_bytes(HTTPStatus.OK, OVERLAY_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/v1/face-state":
            with state_lock:
                payload = dict(latest)
            self._send_json(HTTPStatus.OK, payload)
            return

        if path.startswith("/") and path.endswith(".png"):
            candidate = ROOT / path.lstrip("/")
            if candidate.exists() and candidate.is_file() and candidate.parent == ROOT:
                self._send_bytes(HTTPStatus.OK, candidate.read_bytes(), "image/png")
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "frame not found"})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/v1/health-sample":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        payload = json.loads(raw.decode("utf-8") if raw else "{}")

        health_percent = int(payload.get("health_percent", 100))
        confidence = float(payload.get("confidence", 1.0))

        if confidence < 0.70:
            with state_lock:
                held = dict(latest)
            self._send_json(HTTPStatus.ACCEPTED, {"held": True, "state": held})
            return

        st = engine.update(max(0, min(100, health_percent)))
        out = {
            "frame": st.frame_name,
            "health_percent": st.health_percent,
            "health_bucket": st.health_bucket,
            "look": st.look,
            "is_pain": st.is_pain,
            "updated_at_ms": int(time.time() * 1000),
        }

        with state_lock:
            latest.update(out)

        self._send_json(HTTPStatus.OK, {"ok": True, "state": out})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local overlay server running at http://{HOST}:{PORT}")
    print(f"Browser source URL: http://{HOST}:{PORT}/overlay")
    print(f"Health sample endpoint: POST http://{HOST}:{PORT}/v1/health-sample")
    server.serve_forever()


if __name__ == "__main__":
    main()
