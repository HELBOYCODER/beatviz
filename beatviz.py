#!/usr/bin/env python3
"""beatviz — beat-to-video visualizer (free, local alternative to akira player).

Turns an audio file (+ optional MIDI) into a 9:16 MP4. MIDI-aware looks draw the
actual notes; audio looks follow energy and onsets. Tempo/key can come from the
filename, e.g. "loversrock 136 emin.wav".

Usage:
  python3 beatviz.py beat.wav [--midi song.mid] [--look transit|bars|piano|radial|wave]
                      [--out video.mp4] [--list-looks] [--duration 7]
"""

import argparse
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import wave

from PIL import Image
import midilib
import looks as looks_mod
import looks_music

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


# ---------- audio analysis ----------
def analyze_audio(path, fps):
    tmp = None
    if not path.lower().endswith(".wav"):
        tmp = tempfile.mktemp(suffix=".wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path,
                        "-ac", "1", "-ar", "22050", tmp], check=True)
        use = tmp
    else:
        use = path
    w = wave.open(use, "rb")
    nch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if tmp:
        os.unlink(tmp)
    if sw == 2:
        s = struct.unpack(f"<{len(raw)//2}h", raw)
    elif sw == 1:
        s = [b - 128 for b in raw]
    else:
        raise SystemExit(f"unsupported sample width {sw}")
    mono = list(s[::nch])
    frame_n = max(1, int(sr / fps))
    energies = []
    for i in range(0, len(mono), frame_n):
        ch = mono[i:i + frame_n]
        if not ch:
            break
        rms = math.sqrt(sum(v * v for v in ch) / len(ch)) / 32768.0
        energies.append(min(1.0, rms * 4.0))
    peak = max(energies) or 1.0
    return [e / peak for e in energies], sr, mono


def detect_beats(energies, fps):
    beats = []
    for i in range(8, len(energies) - 1):
        avg = sum(energies[i - 8:i]) / 8 or 1e-6
        if energies[i] > 0.45 and energies[i] > avg * 1.5:
            if not beats or i - beats[-1] > fps / 8:
                beats.append(i)
    return beats


def estimate_bpm(beats, fps):
    """Median inter-onset interval -> BPM."""
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


# ---------- pipeline ----------
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
    ap.add_argument("--list-looks", action="store_true")
    args = ap.parse_args()

    if args.list_looks or not args.audio:
        print("available looks:")
        for k in list(looks_mod.LOOKS) + list(looks_music.LOOKS):
            print("  " + k)
        return
    if args.look not in looks_mod.LOOKS and args.look not in looks_music.LOOKS:
        raise SystemExit(f"unknown look '{args.look}'; use --list-looks")

    meta = parse_filename_meta(args.audio)
    fps = args.fps
    print(f"[beatviz] analyzing {args.audio}")
    energies, sr, mono = analyze_audio(args.audio, fps)
    beats = set(detect_beats(energies, fps))
    bpm = meta["bpm"] or estimate_bpm(sorted(beats), fps)
    print(f"[beatviz] {len(energies)} frames · {len(beats)} onsets · "
          f"BPM={bpm or '?'} key={meta['key'] or '?'}")

    midi = None
    if args.midi:
        midi = midilib.MidiFile(args.midi)
        midi.bpm = bpm or 120
        print(f"[beatviz] MIDI: {len(midi.notes)} notes · {len(midi.parts())} parts · "
              f"range {midi.pitch_range()}")

    frames_dir = tempfile.mkdtemp(prefix="beatviz_")
    total = min(int(args.duration * fps), len(energies))
    flash = 0.0
    fn = looks_mod.LOOKS.get(args.look) or looks_music.LOOKS.get(args.look)
    if fn is None:
        raise SystemExit(f"unknown look '{args.look}'; use --list-looks")
    for i in range(total):
        flash = 1.0 if i in beats else max(0.0, flash - 0.15)
        win = [n for n in (midi.notes if midi else [])
               if abs(n.start - i / fps) < 0.05]
        ctx = looks_mod.Ctx(args.width, args.height, i / fps,
                            energies[i] if i < len(energies) else 0.0,
                            flash, midi, win)
        ctx.mono = mono
        ctx.sr = sr
        ctx.bpm = bpm
        ctx.duration = args.duration
        fn(ctx).save(f"{frames_dir}/f{i:05d}.png")
    print(f"[beatviz] rendered {total} frames with look={args.look}")

    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
        "-i", f"{frames_dir}/f%05d.png", "-i", args.audio,
        "-t", str(args.duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-c:a", "aac", "-shortest", args.out], check=True)
    for f in os.listdir(frames_dir):
        os.unlink(os.path.join(frames_dir, f))
    os.rmdir(frames_dir)
    print(f"[beatviz] done -> {args.out}")


if __name__ == "__main__":
    main()
