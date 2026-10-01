#!/usr/bin/env python3
"""beatviz — beat-to-video visualizer (free, local alternative to akira player).

Turns an audio file (+ optional MIDI) into a 9:16 MP4. MIDI-aware looks draw the
actual notes; audio looks follow energy and onsets. Tempo/key can come from the
filename, e.g. "loversrock 136 emin.wav".

v1.4.0 "Studio": lag-free render engine (single pre-analysis pass, cached
spectrum/fonts/noise), multi-format export (--format mp4|h265|webm|gif|webp|png),
full-song beatmap sidecars (.beatviz.json), and precise start/end trimming.

Usage:
  python3 beatviz.py beat.wav [--midi song.mid] [--look transit|bars|piano|...]
                      [--out video.mp4] [--list-looks] [--duration 7]
                      [--start 12.5] [--end 30] [--format mp4] [--auto-trim]
"""

import argparse
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageChops

import beatmap as beatmap_mod
import exportfmt
import midilib
import looks as looks_mod
import looks_music
import looks_graph

# render quality presets
PRESETS = {
    "fast":    {"ss": 1, "crf": 20, "bitrate": None, "dither": 0.0},
    "high":    {"ss": 2, "crf": 18, "bitrate": None, "dither": 0.5},
    "quality": {"ss": 2, "crf": 16, "bitrate": "12M", "dither": 1.0},
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# ---------- filename metadata ----------
def parse_filename_meta(path):
    """Extract tempo (BPM) and key from a filename like 'loversrock 136 emin.wav'."""
    name = os.path.splitext(os.path.basename(path))[0]
    meta = {"bpm": None, "key": None}
    m = re.search(r"(?<!\d)(\d{2,3})(?!\d)", name)
    if m:
        v = int(m.group(1))
        if 40 <= v <= 300:
            meta["bpm"] = v
    km = re.search(r"\b([a-g])(#|b|s)?\s*(maj|min|m)?\b", name.lower())
    if km:
        letter = km.group(1).upper()
        acc = {"#": "#", "b": "b", "s": "#"}.get(km.group(2) or "", "")
        mode = {"maj": "major", "m": "minor", "min": "minor"}.get(km.group(3) or "", "")
        meta["key"] = f"{letter}{acc} {mode}".strip()
    return meta


# ---------- audio analysis (legacy light API kept for compatibility) ----------
def analyze_audio(path, fps):
    """Legacy API: (energies list, sr, mono list). Prefer beatmap.load_beatmap()."""
    x, sr = beatmap_mod.load_mono(path)
    e = beatmap_mod.frame_energies(x, sr, fps)
    return [float(v) for v in e], sr, [float(v) for v in x]


def detect_beats(energies, fps):
    beats = []
    for i in range(8, len(energies) - 1):
        avg = sum(energies[i - 8:i]) / 8 or 1e-6
        if energies[i] > 0.45 and energies[i] > avg * 1.5:
            if not beats or i - beats[-1] > fps / 8:
                beats.append(i)
    return beats


def estimate_bpm(beats, fps):
    if len(beats) < 4:
        return None
    intervals = [(beats[i + 1] - beats[i]) / fps for i in range(len(beats) - 1)]
    intervals = [iv for iv in intervals if iv > 0]
    if not intervals:
        return None
    intervals.sort()
    med = intervals[len(intervals) // 2]
    while med > 1.0:
        med /= 2
    return round(60.0 / med) if med > 0 else None


# ---------- dithering (cached noise planes — v1.4) ----------
_NOISE_CACHE = {}


def add_dither(img, strength=1.0):
    """Subtle symmetric noise dithering to eliminate gradient banding."""
    key = img.size
    planes = _NOISE_CACHE.get(key)
    if planes is None:
        noise = Image.effect_noise(img.size, 8.0).convert("L")
        pos = noise.point(lambda v: round((v - 128) / 3) if v > 128 else 0).convert("RGB")
        neg = noise.point(lambda v: round((128 - v) / 3) if v <= 128 else 0).convert("RGB")
        planes = (pos, neg)
        _NOISE_CACHE[key] = planes
    return ImageChops.subtract(ImageChops.add(img, planes[0]), planes[1])


# ---------- pipeline ----------
def get_look(name):
    for mod in (looks_mod, looks_music, looks_graph):
        if name in mod.LOOKS:
            return mod.LOOKS[name]
    return None


def all_look_names():
    return list(looks_mod.LOOKS) + list(looks_music.LOOKS) + list(looks_graph.LOOKS)


def render_segment(audio_path, look, out, duration=7.0, width=1080, height=1920,
                   fps=60, preset="quality", ss=None, dither=None, fmt="mp4",
                   start=0.0, end=None, auto_trim=False, midi_path=None,
                   beatmap=None, spectrum=None, frames_keep=None, quiet=False,
                   crf=None, tag=""):
    """Render [start, end) of audio with `look` into `out` in format `fmt`.

    beatmap: precomputed beatmap dict (skips re-analysis).
    spectrum: precomputed (matrix, sr, fps) tuple for spectrum_at fast path.
    Returns (out_path, n_frames).
    """
    import time as _time
    t0 = _time.time()

    if look not in all_look_names():
        raise SystemExit(f"unknown look '{look}'; use --list-looks")
    fn = get_look(look)

    meta = parse_filename_meta(audio_path)

    if beatmap is None:
        beatmap = beatmap_mod.load_beatmap(audio_path, fps)
    bpm = meta["bpm"] or beatmap.get("bpm")
    beats_sec = beatmap.get("beats", [])
    energy = beatmap.get("energy", [])
    bm_fps = beatmap.get("fps", fps)
    song_dur = beatmap.get("duration") or 0.0

    if auto_trim and end is None and song_dur:
        end = song_dur
    if end is None:
        end = start + duration
    seg_dur = max(0.05, end - start)

    midi = None
    if midi_path and os.path.exists(midi_path):
        midi = midilib.MidiFile(midi_path)
        midi.bpm = bpm or 120

    # single analysis pass: numpy spectrum matrix for the whole song
    if spectrum is None:
        x, sr = beatmap_mod.load_mono(audio_path)
        spec = beatmap_mod.spectrum_matrix(x, sr, bm_fps)
        spectrum = (spec, sr, bm_fps)
    looks_music.set_spectrum_matrix(spectrum[0], spectrum[1], spectrum[2])

    work_dir = tempfile.mkdtemp(prefix="beatviz_")
    total = int(seg_dur * fps)
    flash = 0.0
    beat_set = set()
    for b in beats_sec:
        if b >= start:
            i = round((b - start) * fps)
            if 0 <= i < total:
                beat_set.add(i)

    pre = PRESETS[preset]
    ss_v = ss or pre["ss"]
    dith = dither if dither is not None else pre["dither"]
    rw, rh = width * ss_v, height * ss_v
    e_off = int(start * bm_fps)

    out_p = os.path.abspath(out)
    _fmt_ext = exportfmt.FORMATS[fmt][2] if fmt in exportfmt.FORMATS else ".mp4"
    if not out_p.lower().endswith(_fmt_ext):
        out_p = os.path.splitext(out_p)[0] + _fmt_ext
    if fmt == "png":
        frames_dir = work_dir
        enc = None
    else:
        frames_dir = None
        # stream raw RGB frames into ffmpeg — no PNG files, no disk pressure
        if fmt == "gif":
            enc_cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo",
                       "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                       "-r", str(fps), "-i", "pipe:0", "-lavfi",
                       "split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];"
                       "[s1][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle",
                       "-loop", "0", out_p]
        else:
            fmt_args = exportfmt.FORMATS[fmt][1]
            # all output opts must come AFTER every input (per-input opts would
            # otherwise leak into the audio input and break parsing)
            enc_cmd = ["ffmpeg", "-y", "-v", "error",
                       "-f", "rawvideo", "-pix_fmt", "rgb24",
                       "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
            out_opts = []
            if fmt_args[0] == "libx264":
                out_opts += ["-preset", "slow", "-crf", str(crf or pre["crf"]),
                             "-profile:v", "high"]
            elif fmt_args[0] == "libx265":
                out_opts += ["-preset", "slow", "-crf", str((crf or pre["crf"]) + 2)]
            elif fmt_args[0] == "libwebp_anim":
                out_opts += ["-compression_level", "5"]
            out_opts += ["-c:v", fmt_args[0]]
            out_opts += [a for i, a in enumerate(fmt_args[1:])
                         if a != "-pix_fmt" and (i == 0 or fmt_args[1:][i-1] != "-pix_fmt")]
            out_opts += ["-pix_fmt", "yuv420p"] if "-pix_fmt" in fmt_args[1:] else []
            # audio (mp4/h265/webm only)
            audio_codec = ["-c:a", "libopus", "-b:a", "192k"] if fmt == "webm" \
                else ["-c:a", "aac", "-b:a", "256k"]
            if exportfmt.FORMATS[fmt][3]:
                seg_audio = os.path.join(work_dir, "seg." + ("opus" if fmt == "webm" else "m4a"))
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", audio_path,
                                "-ss", str(start), "-t", str(seg_dur), "-vn"] +
                               audio_codec + [seg_audio], check=True)
                enc_cmd += ["-i", seg_audio]
                out_opts += audio_codec + ["-shortest"]
            enc_cmd += out_opts
            enc_cmd += ["-r", str(fps), out_p]
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)

    for i in range(total):
        flash = 1.0 if i in beat_set else max(0.0, flash - 0.15)
        ei = e_off + i
        e = energy[ei] if 0 <= ei < len(energy) else 0.0
        win = [n for n in (midi.notes if midi else [])
               if abs(n.start - (start + i / fps)) < 0.05]
        ctx = looks_mod.Ctx(rw, rh, start + i / fps, e, flash, midi, win)
        ctx.mono = None  # not needed: spectrum_at uses the matrix fast path
        ctx.sr = spectrum[1]
        ctx.bpm = bpm
        ctx.duration = seg_dur
        img = fn(ctx)
        if dith > 0:
            img = add_dither(img, dith)
        if ss_v > 1:
            img = img.resize((width, height), Image.LANCZOS)
        if enc is not None:
            enc.stdin.write(img.convert("RGB").tobytes())
        else:
            img.save(f"{frames_dir}/f{i:05d}.png")
    if enc is not None:
        enc.stdin.close()
        enc.wait()
        if enc.returncode != 0:
            raise RuntimeError(f"ffmpeg encode failed rc={enc.returncode}")
    if not quiet:
        el = _time.time() - t0
        print(f"[beatviz{tag}] rendered {total} frames look={look} "
              f"({start:.2f}s-{end:.2f}s, preset={preset}, ss={ss_v}, fmt={fmt}) "
              f"in {el:.1f}s ({total / el:.1f} fps)")

    if fmt == "png":
        import zipfile
        with zipfile.ZipFile(out_p if out_p.endswith(".zip") else out_p + ".zip",
                             "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(frames_dir)):
                z.write(os.path.join(frames_dir, f), arcname=f)
        out_p = out_p if out_p.endswith(".zip") else out_p + ".zip"
        for f in os.listdir(frames_dir):
            os.unlink(os.path.join(frames_dir, f))
    for d in filter(None, (frames_dir, work_dir)):
        if d and os.path.isdir(d):
            for f in os.listdir(d):
                os.unlink(os.path.join(d, f))
            os.rmdir(d)
    looks_music.clear_spectrum_matrix()
    return out_p, total


def main():
    ap = argparse.ArgumentParser(description="beatviz — beat to video")
    ap.add_argument("audio", nargs="?")
    ap.add_argument("--midi")
    ap.add_argument("--look", default="transit")
    ap.add_argument("--out", default="beatviz_out.mp4")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=7.0)
    ap.add_argument("--preset", choices=list(PRESETS), default="quality",
                    help="render quality preset (default: quality = 2x supersampling, CRF 16)")
    ap.add_argument("--ss", type=int, default=None, choices=[1, 2, 3],
                    help="supersampling factor override (render at Nx, downscale LANCZOS)")
    ap.add_argument("--dither", type=float, default=None, metavar="0-2",
                    help="subtle dithering strength to kill banding (0=off)")
    ap.add_argument("--format", default="mp4",
                    choices=list(exportfmt.FORMATS),
                    help="export format: mp4 (h264) | h265 | webm (vp9) | gif | webp | png zip")
    ap.add_argument("--start", type=float, default=0.0,
                    metavar="SEC", help="start time in seconds (aligned to beatmap)")
    ap.add_argument("--end", "--to", dest="end", type=float, default=None,
                    metavar="SEC", help="end time in seconds (default: start+duration)")
    ap.add_argument("--auto-trim", action="store_true",
                    help="sync output duration to the full song length")
    ap.add_argument("--beatmap", action="store_true",
                    help="force (re)build the .beatviz.json sidecar and exit")
    ap.add_argument("--list-looks", action="store_true")
    args = ap.parse_args()

    if args.list_looks or not args.audio:
        print("available looks:")
        for k in all_look_names():
            print("  " + k)
        return

    if args.beatmap:
        side = os.path.splitext(args.audio)[0] + ".beatviz.json"
        bm = beatmap_mod.build_beatmap(args.audio, args.fps, side)
        print(f"beatmap: {len(bm['beats'])} beats · BPM={bm['bpm']} -> {side}")
        return

    out, n = render_segment(
        args.audio, args.look, args.out, duration=args.duration,
        width=args.width, height=args.height, fps=args.fps, preset=args.preset,
        ss=args.ss, dither=args.dither, fmt=args.format, start=args.start,
        end=args.end, auto_trim=args.auto_trim, midi_path=args.midi)
    print(f"[beatviz] done -> {out}")


if __name__ == "__main__":
    main()
