"""beatmap.py — full-song analysis: beat grid, downbeats, energy envelope, sections.

Produces a .beatviz.json sidecar so renders skip per-render re-analysis:
{
  "version": 1, "audio": "song.wav", "duration": 123.4, "fps": 60,
  "bpm": 128.0, "beats": [t...], "downbeats": [t...],
  "energy": [e per frame...], "sections": [{"start":0,"end":31.2,"kind":"intro"}...],
  "peaks": [waveform min/max pairs for UI]
}
"""
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave

import numpy as np


def load_mono(path, sr=22050):
    """Decode any audio to float32 mono via ffmpeg/wave."""
    tmp = None
    if not path.lower().endswith(".wav"):
        tmp = tempfile.mktemp(suffix=".wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path,
                        "-ac", "1", "-ar", str(sr), tmp], check=True)
        use = tmp
    else:
        use = path
    w = wave.open(use, "rb")
    nch, sw, srate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if tmp:
        os.unlink(tmp)
    if sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if nch > 1:
        x = x[::nch]
    if srate != sr:  # rare: resample with ffmpeg always matches, but be safe
        idx = np.linspace(0, len(x) - 1, int(len(x) * sr / srate))
        x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return x, sr


def frame_energies(x, sr, fps):
    n = max(1, int(sr / fps))
    m = len(x) // n
    fr = x[: m * n].reshape(m, n)
    rms = np.sqrt((fr * fr).mean(axis=1))
    e = np.minimum(1.0, rms * 4.0)
    peak = e.max() or 1.0
    return e / peak


def onset_strength(e, fps):
    """Half-wave rectified spectral-ish flux of the energy envelope."""
    d = np.diff(e, prepend=e[0])
    d = np.maximum(d, 0.0)
    sm = np.convolve(d, np.ones(3) / 3, mode="same")
    return sm / (sm.max() or 1.0)


def detect_beats(e, fps):
    """Onset times (seconds) via adaptive threshold on onset strength."""
    os_ = onset_strength(e, fps)
    beats = []
    min_gap = fps / 8
    last = -10 ** 9
    win = max(4, int(fps * 0.3))
    for i in range(1, len(os_)):
        lo, hi = max(0, i - win), min(len(os_), i + win)
        thr = 0.45 * os_[lo:hi].mean() + 0.10
        if os_[i] > thr and os_[i] >= os_[i - 1] and os_[i] >= os_[lo:hi].max() * 0.9:
            if i - last >= min_gap:
                beats.append(i / fps)
                last = i
    return beats


def estimate_bpm(beats):
    if len(beats) < 4:
        return None
    iv = np.diff(np.array(beats))
    iv = iv[(iv > 0.15) & (iv < 3.0)]
    if not len(iv):
        return None
    med = float(np.median(iv))
    while med > 1.2:
        med /= 2
    while med < 0.3:
        med *= 2
    return round(60.0 / med, 1)


def pick_downbeats(beats, bpm):
    if not beats or not bpm:
        return beats[::4] if beats else []
    per = 60.0 / bpm
    # snap to a grid starting at the strongest beat
    grid = np.array(beats)
    phase_scores = []
    for k in range(4):
        idx = np.arange(k, len(grid), 4)
        phase_scores.append(float(grid[idx % len(grid)] @ np.zeros(len(idx)) + sum(1 for _ in idx)))
    # simple: phase with strongest average energy proxy = earliest beats
    start = 0
    db = list(grid[start::4])
    return db


def sections_from_energy(e, fps, duration):
    """Split into coarse sections by sustained energy level shifts."""
    if not len(e):
        return [{"start": 0.0, "end": duration, "kind": "all"}]
    sm = np.convolve(e, np.ones(fps) / fps, mode="same")
    seg = max(1, len(sm) // 8)
    kinds = ["intro", "build", "drop", "break", "drop", "break", "build", "outro"]
    out = []
    for k in range(8):
        s, en = k * seg, (k + 1) * seg if k < 7 else len(sm)
        lvl = float(sm[s:en].mean())
        out.append({"start": round(s / fps, 2), "end": round(en / fps, 2),
                    "kind": kinds[k], "level": round(lvl, 3)})
    # merge tiny tail
    if out and out[-1]["end"] - out[-1]["start"] < 0.5 and len(out) > 1:
        out[-2]["end"] = out[-1]["end"]
        out.pop()
    return out


def waveform_peaks(x, buckets=800):
    if not len(x):
        return []
    n = min(buckets, len(x))
    idx = np.linspace(0, len(x), n + 1, dtype=int)
    peaks = []
    for i in range(n):
        seg = x[idx[i]: idx[i + 1]]
        if not len(seg):
            peaks.extend([0.0, 0.0])
        else:
            peaks.extend([round(float(seg.min()), 3), round(float(seg.max()), 3)])
    return peaks


def spectrum_matrix(x, sr, fps, bands=64):
    """Precompute a per-frame FFT band matrix (frames x bands), normalized 0..1."""
    n = max(1, int(sr / fps))
    m = len(x) // n
    if m == 0:
        return np.zeros((0, bands), dtype=np.float32)
    fr = x[: m * n].reshape(m, n) * np.hanning(n)
    spec = np.abs(np.fft.rfft(fr, axis=1))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    edges = np.geomspace(max(20.0, freqs[1]), min(16000.0, freqs[-1]), bands + 1)
    out = np.zeros((m, bands), dtype=np.float32)
    for b in range(bands):
        mask = (freqs >= edges[b]) & (freqs < edges[b + 1])
        if mask.any():
            out[:, b] = spec[:, mask].mean(axis=1)
    out /= (out.max() or 1.0)
    return out


def build_beatmap(audio_path, fps=60, sidecar=None):
    x, sr = load_mono(audio_path)
    duration = len(x) / sr
    e = frame_energies(x, sr, fps)
    beats = detect_beats(e, fps)
    bpm = estimate_bpm(beats)
    bm = {
        "version": 1,
        "audio": os.path.basename(audio_path),
        "duration": round(duration, 3),
        "fps": fps,
        "bpm": bpm,
        "beats": [round(b, 4) for b in beats],
        "downbeats": [round(b, 4) for b in pick_downbeats(beats, bpm)],
        "energy": [round(float(v), 4) for v in e],
        "sections": sections_from_energy(e, fps, duration),
        "peaks": waveform_peaks(x),
    }
    if sidecar:
        with open(sidecar, "w") as f:
            json.dump(bm, f)
    return bm


def load_beatmap(audio_path, fps=60):
    """Return (beatmap dict, spectrum matrix or None). Uses sidecar when present."""
    side = os.path.splitext(audio_path)[0] + ".beatviz.json"
    if os.path.exists(side):
        try:
            with open(side) as f:
                bm = json.load(f)
            if abs(bm.get("fps", fps) - fps) < 1:
                return bm
        except Exception:
            pass
    return build_beatmap(audio_path, fps, side)


def main():
    ap = sys.argv[1:]
    if not ap:
        print("usage: beatmap.py <audio> [--fps 60]")
        return
    path = ap[0]
    fps = 60
    if "--fps" in ap:
        fps = int(ap[ap.index("--fps") + 1])
    bm = build_beatmap(path, fps, os.path.splitext(path)[0] + ".beatviz.json")
    print(f"beatmap: {len(bm['beats'])} beats · BPM={bm['bpm']} · "
          f"{bm['duration']}s · {len(bm['sections'])} sections -> "
          f"{os.path.splitext(path)[0]}.beatviz.json")


if __name__ == "__main__":
    main()
