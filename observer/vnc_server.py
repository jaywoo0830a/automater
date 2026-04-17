"""Tiny HTTP server exposing active VNC worker sessions.

Runs inside the observer container on port 7070.
The API layer proxies /observer/vnc/* to this server.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from observer.vnc import list_active

logger = logging.getLogger(__name__)

_PORT = 7070


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/workers":
            data = list_active()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress noisy access logs


def start_vnc_server() -> None:
    """Start the VNC status server in a background thread."""
    server = HTTPServer(("0.0.0.0", _PORT), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("VNC status server started on port %d", _PORT)
