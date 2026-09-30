#!/usr/bin/env python3
"""BeatViz app backend: local HTTP server + render engine for the Electron UI.

Endpoints:
  GET  /            -> app UI
  GET  /api/looks   -> JSON list of all templates
  POST /api/render  -> {audio_b64, look, duration, width, height} -> {job_id}
  GET  /api/job/<id>-> {status, progress, video}
  GET  /video/<name>-> rendered mp4
"""
import base64
import json
import os
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import midilib
import looks as looks_mod
import looks_music
import templates_pack1
import templates_pack2

ALL_LOOKS = {}
for mod in (looks_mod, looks_music, templates_pack1, templates_pack2):
    for k, v in mod.LOOKS.items():
        ALL_LOOKS[k] = v

JOBS = {}
OUT_DIR = os.path.join(tempfile.gettempdir(), "beatviz_out")
os.makedirs(OUT_DIR, exist_ok=True)
UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_ui.html")


def run_render(job_id, audio_path, look, duration, width, height):
    try:
        import wave
        import math
        import struct
        import subprocess
        from PIL import Image

        JOBS[job_id]["status"] = "analyzing"
        # reuse beatviz.analyze via import
        import importlib
        bv = importlib.import_module("beatviz")
        energies, sr, mono = bv.analyze_audio(audio_path, 30)
        beats = set(bv.detect_beats(energies, 30))
        meta = bv.parse_filename_meta(audio_path)
        bpm = meta["bpm"] or bv.estimate_bpm(sorted(beats), 30)

        midi = None
        midi_path = audio_path.rsplit(".", 1)[0] + ".mid"
        if os.path.exists(midi_path):
            midi = midilib.MidiFile(midi_path)

        fn = ALL_LOOKS[look]
        frames_dir = tempfile.mkdtemp(prefix="bv_")
        total = min(int(duration * 30), len(energies))
        flash = 0.0
        for i in range(total):
            flash = 1.0 if i in beats else max(0.0, flash - 0.15)
            ctx = looks_mod.Ctx(width, height, i / 30,
                                energies[i] if i < len(energies) else 0.0,
                                flash, midi, [])
            ctx.mono, ctx.sr, ctx.bpm, ctx.duration = mono, sr, bpm, duration
            fn(ctx).save(f"{frames_dir}/f{i:05d}.png")
            if i % 30 == 0:
                JOBS[job_id]["progress"] = round(30 + 60 * i / max(1, total))
        out = os.path.join(OUT_DIR, f"{job_id}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-framerate", "30",
            "-i", f"{frames_dir}/f%05d.png", "-i", audio_path,
            "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", "30", "-c:a", "aac", "-shortest", out], check=True)
        for f in os.listdir(frames_dir):
            os.unlink(os.path.join(frames_dir, f))
        os.rmdir(frames_dir)
        JOBS[job_id].update(status="done", progress=100, video=os.path.basename(out))
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
            body = open(UI_PATH, "rb").read()
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
                body = open(p, "rb").read()
                self._send(200, body, "video/mp4")
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
            ext = ".wav" if req.get("audio_name", "").endswith(".wav") else ".mp3"
            ap = os.path.join(OUT_DIR, f"in_{jid}{ext}")
            open(ap, "wb").write(audio)
            JOBS[jid] = {"status": "queued", "progress": 5}
            threading.Thread(target=run_render,
                             args=(jid, ap, req["look"],
                                   min(float(req.get("duration", 15)), 300),
                                   int(req.get("width", 1920)),
                                   int(req.get("height", 1080))),
                             daemon=True).start()
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
