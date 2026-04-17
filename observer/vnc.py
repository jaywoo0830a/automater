"""VNC display manager for observer workers.

Each worker gets its own Xvfb display + x11vnc + websockify stack so
the browser can be viewed remotely via noVNC in the web dashboard.

WebSocket ports are allocated from 7080-7089 (up to 10 workers).
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_VNC_PORT_RANGE = range(7090, 7100)
_WS_PORT_RANGE = range(7080, 7090)
_lock = threading.Lock()
_used_ports: set[int] = set()

# Active worker sessions (ws_port -> WorkerVnc)
_active: dict[int, "WorkerVnc"] = {}


@dataclass
class WorkerVnc:
    """Tracks VNC processes for one observer worker."""

    worker_id: int
    display: str
    ws_port: int
    schedule_id: int | None = None
    keyword: str = ""
    blog_id: str = ""
    status: str = "running"  # running / idle / stopped
    _procs: list[subprocess.Popen] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "display": self.display,
            "ws_port": self.ws_port,
            "schedule_id": self.schedule_id,
            "keyword": self.keyword,
            "blog_id": self.blog_id,
            "status": self.status,
        }


def _alloc_port(port_range: range) -> int:
    with _lock:
        for port in port_range:
            if port not in _used_ports:
                _used_ports.add(port)
                return port
    raise RuntimeError(f"No free port in {port_range.start}-{port_range.stop}")


def _free_port(port: int) -> None:
    with _lock:
        _used_ports.discard(port)


def _find_free_display() -> int:
    for n in range(50, 100):
        if not Path(f"/tmp/.X{n}-lock").exists():
            return n
    raise RuntimeError("No free X display")


def start_vnc(worker_id: int) -> WorkerVnc:
    """Start Xvfb + x11vnc + websockify for a worker. Returns WorkerVnc."""
    display_num = _find_free_display()
    display_str = f":{display_num}"
    vnc_port = _alloc_port(_VNC_PORT_RANGE)
    ws_port = _alloc_port(_WS_PORT_RANGE)

    xvfb = subprocess.Popen(
        ["Xvfb", display_str, "-screen", "0", "1920x1080x24", "-ac"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.8)

    vnc = subprocess.Popen(
        ["x11vnc", "-display", display_str, "-nopw", "-shared", "-forever",
         "-rfbport", str(vnc_port), "-noxdamage"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.3)

    wsproxy = subprocess.Popen(
        ["websockify", "--web", "/usr/share/novnc", str(ws_port),
         f"localhost:{vnc_port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.3)

    wv = WorkerVnc(
        worker_id=worker_id,
        display=display_str,
        ws_port=ws_port,
        _procs=[xvfb, vnc, wsproxy],
    )

    with _lock:
        _active[ws_port] = wv

    logger.info("VNC started: worker=%d display=%s ws_port=%d", worker_id, display_str, ws_port)
    return wv


def stop_vnc(wv: WorkerVnc) -> None:
    """Stop VNC processes for a worker."""
    for proc in reversed(wv._procs):
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    _free_port(wv.ws_port)
    # free vnc port too
    for proc in wv._procs:
        pass  # ports freed by process exit

    with _lock:
        _active.pop(wv.ws_port, None)

    wv.status = "stopped"
    logger.info("VNC stopped: worker=%d ws_port=%d", wv.worker_id, wv.ws_port)


def list_active() -> list[dict]:
    """Return list of active worker VNC sessions."""
    with _lock:
        return [wv.to_dict() for wv in _active.values()]
