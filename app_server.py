#!/usr/bin/env python3
"""BeatViz app backend: local HTTP server + render engine for the Electron UI.

v1.4.0: lag-free engine (precomputed spectrum, streamed frames — no PNG files),
multi-format export, full-song beatmaps, start/end trimming.

Endpoints:
  GET  /              -> app UI
  GET  /api/looks     -> JSON list of all templates
  POST /api/render    -> {audio_b64, audio_name, look, duration, width, height,
                          fps, preset, format, start, end, auto_trim} -> {job_id}
  GET  /api/job/<id>  -> {status, progress, video, beatmap}
  GET  /video/<name>  -> rendered file
"""
import base64
import json
import os
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import beatmap as beatmap_mod
import beatviz
import looks as looks_mod
import looks_music
import looks_graph
import templates_pack1
import templates_pack2

ALL_LOOKS = {}
for mod in (looks_mod, looks_music, looks_graph, templates_pack1, templates_pack2):
    ALL_LOOKS.update(mod.LOOKS)

JOBS = {}
OUT_DIR = os.path.join(tempfile.gettempdir(), "beatviz_out")
os.makedirs(OUT_DIR, exist_ok=True)
UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_ui.html")

_CTYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".gif": "image/gif",
           ".webp": "image/webp", ".zip": "application/zip"}


def run_render(job_id, audio_path, opts):
    try:
        JOBS[job_id]["status"] = "analyzing"
        bm = beatmap_mod.load_beatmap(audio_path, int(opts.get("fps", 30)))
        JOBS[job_id]["beatmap"] = {
            "bpm": bm.get("bpm"), "duration": bm.get("duration"),
            "beats": len(bm.get("beats", [])), "sections": bm.get("sections", []),
        }
        JOBS[job_id]["status"] = "rendering"
        t0 = time.time()
        out, n = beatviz.render_segment(
            audio_path, opts["look"], os.path.join(OUT_DIR, job_id),
            duration=float(opts.get("duration", 15)),
            width=int(opts.get("width", 1920)),
            height=int(opts.get("height", 1080)),
            fps=int(opts.get("fps", 30)),
            preset=opts.get("preset", "quality"),
            fmt=opts.get("format", "mp4"),
            start=float(opts.get("start", 0.0)),
            end=opts.get("end"),
            auto_trim=bool(opts.get("auto_trim")),
            beatmap=bm, quiet=True)
        JOBS[job_id].update(status="done", progress=100,
                            video=os.path.basename(out), frames=n,
                            render_seconds=round(time.time() - t0, 1))
    except Exception as e:
        JOBS[job_id].update(status="error", error=str(e))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(UI_PATH, "rb") as f:
                body = f.read()
            self._send(200, body, "text/html; charset=utf-8")
        elif self.path == "/api/looks":
            items = []
            for mod, prefix in ((looks_mod, "کلاسیک / Classic"),
                                (looks_music, "موزیکال / Musical"),
                                (templates_pack1, "حرفه‌ای / Pro"),
                                (templates_pack2, "خاص / Special")):
                for k, fn in mod.LOOKS.items():
                    desc = (fn.__doc__ or k).strip().splitlines()[0]
                    items.append({"id": k, "group": prefix, "desc": desc})
            self._send(200, json.dumps({"looks": items}).encode())
        elif self.path.startswith("/api/job/"):
            jid = self.path.split("/")[-1]
            self._send(200, json.dumps(JOBS.get(jid, {"status": "unknown"})).encode())
        elif self.path.startswith("/video/"):
            name = os.path.basename(self.path)
            p = os.path.join(OUT_DIR, name)
            if os.path.exists(p):
                ctype = _CTYPES.get(os.path.splitext(name)[1], "application/octet-stream")
                with open(p, "rb") as f:
                    body = f.read()
                self._send(200, body, ctype)
            else:
                self._send(404, b"{}")
        else:
            self._send(404, b"{}")

    def do_POST(self):
        if self.path == "/api/render":
            ln = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(ln))
            jid = uuid.uuid4().hex[:10]
            audio = base64.b64decode(req["audio_b64"])
            ext = os.path.splitext(req.get("audio_name", "in.wav"))[1].lower() or ".wav"
            ap = os.path.join(OUT_DIR, f"in_{jid}{ext}")
            with open(ap, "wb") as f:
                f.write(audio)
            req["duration"] = min(float(req.get("duration", 15)), 600)
            JOBS[jid] = {"status": "queued", "progress": 5}
            threading.Thread(target=run_render, args=(jid, ap, req), daemon=True).start()
            self._send(200, json.dumps({"job_id": jid}).encode())
        else:
            self._send(404, b"{}")


def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"beatviz backend on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
