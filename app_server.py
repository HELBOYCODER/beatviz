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
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import beatmap as beatmap_mod
import beatviz
import exportfmt
import looks as looks_mod
import looks_music
import looks_graph
import templates_pack1
import templates_pack2

VERSION = "1.4.0"

ALL_LOOKS = {}
for mod in (looks_mod, looks_music, looks_graph, templates_pack1, templates_pack2):
    ALL_LOOKS.update(mod.LOOKS)

JOBS = {}
OUT_DIR = os.path.join(tempfile.gettempdir(), "beatviz_out")
os.makedirs(OUT_DIR, exist_ok=True)
UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_ui.html")

_CTYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".gif": "image/gif",
           ".webp": "image/webp", ".zip": "application/zip"}
PREVIEW = {"width": 540, "height": 960, "fps": 30}


def run_playlist(job_id, audio_path, segments, fmt, width, height, fps, preset):
    try:
        parts = []
        for i, seg in enumerate(segments):
            JOBS[job_id].update(status=f"segment {i + 1}/{len(segments)}",
                                progress=int(90 * i / max(1, len(segments))))
            p, _ = beatviz.render_segment(
                audio_path, seg["look"], os.path.join(OUT_DIR, f"{job_id}_s{i}"),
                duration=seg["end"] - seg["start"], width=width, height=height,
                fps=fps, preset=preset, fmt=fmt,
                start=float(seg["start"]), end=float(seg["end"]), quiet=True)
            parts.append(p)
        JOBS[job_id]["status"] = "concatenating"
        JOBS[job_id]["progress"] = 95
        out = exportfmt.concat_clips(parts, os.path.join(OUT_DIR, f"{job_id}.mp4"))
        JOBS[job_id].update(status="done", progress=100, video=os.path.basename(out))
    except Exception as e:
        JOBS[job_id].update(status="error", error=str(e)[:300])


def run_analyze(job_id, audio_path, fps=60):
    try:
        JOBS[job_id]["status"] = "analyzing"
        JOBS[job_id]["progress"] = 30
        bm = beatmap_mod.build_beatmap(audio_path, fps)
        JOBS[job_id].update(status="done", progress=100, beatmap=bm)
    except Exception as e:
        JOBS[job_id].update(status="error", error=str(e)[:300])


def render_lookthumb(look_id, w=216, h=384):
    """One representative rendered frame per look, cached on disk."""
    cache = os.path.join(OUT_DIR, f"thumb_{look_id}.png")
    if os.path.exists(cache):
        return cache
    fn = ALL_LOOKS.get(look_id)
    if fn is None:
        return None
    ctx = looks_mod.Ctx(w, h, 1.0, 0.5, 0.7, None, [])
    ctx.mono = [0.0] * 2048
    ctx.sr = 22050
    ctx.bpm = 120
    ctx.duration = 7.0
    fn(ctx).save(cache)
    return cache


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
                                (templates_pack2, "خاص / Special"),
                                (looks_graph, "گراف / Graph")):
                for k, fn in mod.LOOKS.items():
                    desc = (fn.__doc__ or k).strip().splitlines()[0]
                    items.append({"id": k, "group": prefix, "desc": desc})
            self._send(200, json.dumps({"looks": items}).encode())
        elif self.path == "/api/system":
            encs = exportfmt.available_encoders()
            self._send(200, json.dumps({
                "version": VERSION,
                "looks": list(ALL_LOOKS.keys()),
                "encoders": encs,
                "formats": list(exportfmt.FORMATS.keys()),
                "preview": PREVIEW,
            }).encode())
        elif self.path.startswith("/api/lookthumb/"):
            lid = self.path.rsplit("/", 1)[-1]
            try:
                p = render_lookthumb(lid)
                if p and os.path.exists(p):
                    with open(p, "rb") as f:
                        self._send(200, f.read(), "image/png")
                else:
                    self._send(404, b'{"error":"unknown look"}')
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)[:200]}).encode())
        elif self.path.startswith("/api/beatmap/"):
            jid = self.path.rsplit("/", 1)[-1]
            j = JOBS.get(jid, {})
            self._send(200, json.dumps({
                "status": j.get("status", "unknown"),
                "beatmap": j.get("beatmap")}).encode())
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
        if self.path in ("/api/render", "/api/preview"):
            ln = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(ln))
            except Exception:
                self._send(400, b'{"error":"invalid JSON"}')
                return
            if req.get("look") not in ALL_LOOKS:
                self._send(400, json.dumps(
                    {"error": f"unknown look '{req.get('look')}'"}).encode())
                return
            jid = uuid.uuid4().hex[:10]
            audio = base64.b64decode(req["audio_b64"])
            ext = os.path.splitext(req.get("audio_name", "in.wav"))[1].lower() or ".wav"
            ap = os.path.join(OUT_DIR, f"in_{jid}{ext}")
            with open(ap, "wb") as f:
                f.write(audio)
            preview = self.path == "/api/preview"
            if preview:
                req["width"], req["height"], req["fps"] = (
                    PREVIEW["width"], PREVIEW["height"], PREVIEW["fps"])
                req["preset"] = "fast"
            req["duration"] = min(float(req.get("duration", 15)), 600)
            JOBS[jid] = {"status": "queued", "progress": 5, "preview": preview}
            threading.Thread(target=run_render, args=(jid, ap, req), daemon=True).start()
            self._send(200, json.dumps({"job_id": jid}).encode())
        elif self.path == "/api/playlist":
            ln = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(ln))
            except Exception:
                self._send(400, b'{"error":"invalid JSON"}')
                return
            segs = req.get("segments") or []
            if not segs or any(s.get("look") not in ALL_LOOKS for s in segs):
                self._send(400, b'{"error":"segments with valid looks required"}')
                return
            jid = uuid.uuid4().hex[:10]
            audio = base64.b64decode(req["audio_b64"])
            ext = os.path.splitext(req.get("audio_name", "in.wav"))[1].lower() or ".wav"
            ap = os.path.join(OUT_DIR, f"in_{jid}{ext}")
            with open(ap, "wb") as f:
                f.write(audio)
            JOBS[jid] = {"status": "queued", "progress": 5}
            threading.Thread(target=run_playlist, daemon=True, args=(
                jid, ap, segs, req.get("format", "mp4"),
                int(req.get("width", 1080)), int(req.get("height", 1920)),
                int(req.get("fps", 60)), req.get("preset", "quality"))).start()
            self._send(200, json.dumps({"job_id": jid}).encode())
        elif self.path == "/api/analyze":
            ln = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(ln))
            except Exception:
                self._send(400, b'{"error":"invalid JSON"}')
                return
            jid = uuid.uuid4().hex[:10]
            audio = base64.b64decode(req["audio_b64"])
            ext = os.path.splitext(req.get("audio_name", "in.wav"))[1].lower() or ".wav"
            ap = os.path.join(OUT_DIR, f"in_{jid}{ext}")
            with open(ap, "wb") as f:
                f.write(audio)
            JOBS[jid] = {"status": "queued", "progress": 5}
            threading.Thread(target=run_analyze, daemon=True, args=(jid, ap)).start()
            self._send(200, json.dumps({"job_id": jid}).encode())
        else:
            self._send(404, b'{"error":"not found"}')


def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"beatviz backend on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
