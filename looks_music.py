"""Music-synced looks for beatviz: beat-bar visualizer locked to the audio.

Frequency-band bars driven by real FFT of the audio (numpy-free radix-2 FFT),
with beat-synced floor glow and melody sparkle.
"""
import math
from PIL import Image, ImageDraw

try:
    from . import midilib
except ImportError:
    import midilib

LINE_COLORS = [
    (229, 72, 77), (62, 99, 221), (18, 165, 148), (247, 107, 21),
    (231, 165, 0), (103, 148, 54), (143, 143, 143), (190, 60, 190),
]
GLOW = [(255, 94, 98), (0, 245, 212), (255, 230, 0), (170, 120, 255)]


def _lerp(a, b, f):
    return int(a + (b - a) * f)


def gradient_color(f, c0=(0, 245, 212), c1=(60, 99, 221), c2=(170, 60, 220)):
    """Frequency-position -> teal->blue->purple gradient."""
    if f < 0.5:
        return (_lerp(c0[0], c1[0], f * 2), _lerp(c0[1], c1[1], f * 2),
                _lerp(c0[2], c1[2], f * 2))
    f = (f - 0.5) * 2
    return (_lerp(c1[0], c2[0], f), _lerp(c1[1], c2[1], f), _lerp(c1[2], c2[2], f))


def _fft(x):
    """Iterative radix-2 FFT (list of floats -> list of complex)."""
    n = len(x)
    if n & (n - 1):
        m = 1
        while m < n:
            m <<= 1
        x = list(x) + [0.0] * (m - n)
        n = m
    j = 0
    a = [complex(v, 0) for v in x]
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        ang = -2 * math.pi / length
        wl = complex(math.cos(ang), math.sin(ang))
        for i in range(0, n, length):
            w = 1 + 0j
            for k in range(length // 2):
                u = a[i + k]
                v = a[i + k + length // 2] * w
                a[i + k] = u + v
                a[i + k + length // 2] = u - v
                w *= wl
        length <<= 1
    return a


def spectrum_at(mono, sr, t, nbands=48, window=2048):
    """Return nbands normalized magnitudes (log-spaced, 40Hz..12kHz) at time t."""
    c = int(t * sr)
    half = window // 2
    seg = mono[max(0, c - half): c + half]
    if len(seg) < window:
        seg = seg + [0.0] * (window - len(seg))
    # hann window
    x = [seg[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / window)) for i in range(window)]
    spec = _fft(x)
    mags = [abs(spec[i]) for i in range(window // 2)]
    bands = []
    fmin, fmax = 40.0, 12000.0
    for b in range(nbands):
        f0 = fmin * (fmax / fmin) ** (b / nbands)
        f1 = fmin * (fmax / fmin) ** ((b + 1) / nbands)
        i0, i1 = int(f0 / sr * window), max(int(f1 / sr * window), int(f0 / sr * window) + 1)
        i0 = min(max(0, i0), window // 2 - 1)
        i1 = min(max(i1, i0 + 1), window // 2)
        m = max(mags[i0:i1]) if i1 > i0 else 0.0
        bands.append(m)
    peak = max(bands) or 1.0
    return [min(1.0, v / peak) for v in bands]


def _font(idx, size):
    paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
    try:
        return ImageFont.truetype(paths[idx], size)
    except Exception:
        return ImageFont.load_default()


from PIL import ImageFont


# ---- LOOK: beat bars — full-width spectrum, centered, beat-glow, clean bg ----
def look_beatbars(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (12, 12, 20))
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=40)

    # centered vertical layout: bars occupy middle 55%
    base_y = int(h * 0.70)
    max_h = int(h * 0.42)
    n = len(spec)
    bw = w / n
    gap = max(2, int(bw * 0.22))
    for i, e in enumerate(spec):
        e = e ** 0.8  # perceptual
        bh = int(max_h * e)
        x = int(i * bw)
        col = gradient_color(i / (n - 1))
        # mirrored: bar grows up from base, soft reflection below
        d.rounded_rectangle([x + gap, base_y - bh, x + bw - gap, base_y],
                            radius=int(bw * 0.18), fill=col)
        refl = int(bh * 0.35)
        dim = tuple(int(c * 0.25) for c in col)
        d.rounded_rectangle([x + gap, base_y + int(h*0.01), x + bw - gap, base_y + int(h*0.01) + refl],
                            radius=int(bw * 0.18), fill=dim)
    # baseline glow that pulses on beats
    glow_a = int(90 * (0.3 + 0.7 * ctx.beat))
    col = tuple(min(255, c + glow_a) for c in (0, 245, 212))
    d.line([(0, base_y), (w, base_y)], fill=col, width=max(2, int(h * 0.002)))

    # now playing label
    f_t = _font(0, int(w * 0.05))
    f_m = _font(1, int(w * 0.020))
    d.text((int(w*0.06), int(h*0.06)), "beatviz", font=f_t, fill=(240, 240, 240))
    bpm = getattr(ctx.midi, "bpm", None) or ctx.bpm or 120
    d.text((int(w*0.06), int(h*0.115)),
           f"{bpm:.0f} BPM · {ctx.t:04.1f}s / {ctx.duration:04.1f}s",
           font=f_m, fill=(160, 160, 170))
    # progress bar
    prog = ctx.t / max(0.01, ctx.duration)
    d.rounded_rectangle([int(w*0.06), int(h*0.145), int(w*0.94), int(h*0.152)],
                        radius=int(h*0.003), fill=(50, 50, 66))
    d.rounded_rectangle([int(w*0.06), int(h*0.145), int(w*0.06 + (w*0.88)*prog), int(h*0.152)],
                        radius=int(h*0.003), fill=LINE_COLORS[2])
    return img


# ---- LOOK: aura rings — concentric rings per band, beat-synced pulse ----
def look_aura(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 10, 18))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.48)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=24)
    n = len(spec)
    for i in range(n):
        e = spec[i] ** 0.9
        r = int((min(w, h) * 0.12) + i * (min(w, h) * 0.028) + e * min(w, h) * 0.05)
        col = LINE_COLORS[i % len(LINE_COLORS)]
        lw = max(3, int(w * 0.006 * (0.5 + e)))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=lw)
    # core that breathes with beat
    r0 = int(min(w, h) * (0.06 + 0.04 * ctx.beat + 0.03 * ctx.energy))
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=GLOW[0])
    f_t = _font(0, int(w * 0.05))
    d.text((int(w*0.06), int(h*0.06)), "beatviz", font=f_t, fill=(240, 240, 240))
    return img


# ---- LOOK: midi melody + spectrum underlay (the harmonized one) ----
def look_melody(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (12, 11, 22))
    d = ImageDraw.Draw(img)
    # underlay: soft spectrum from bottom
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=32)
    base_y = int(h * 0.86)
    bw = w / len(spec)
    for i, e in enumerate(spec):
        bh = int(h * 0.30 * (e ** 0.9))
        col = tuple(int(c * 0.55) for c in LINE_COLORS[i % len(LINE_COLORS)])
        d.rounded_rectangle([int(i * bw) + 2, base_y - bh, int((i + 1) * bw) - 2, base_y],
                            radius=int(bw * 0.2), fill=col)
    # melody: MIDI notes as glowing marbles rolling right->left
    if ctx.midi:
        lo, hi = ctx.midi.pitch_range()
        span = max(1, hi - lo)
        win = 5.0
        for nt in ctx.midi.notes:
            rel = nt.start - ctx.t
            if rel > win or rel < -nt.duration:
                continue
            x = int(w * 0.92 - (rel / win) * w * 0.86)
            y = int(h * 0.10 + (1 - (nt.pitch - lo) / span) * h * 0.42)
            r = int(w * 0.014 * (0.7 + nt.velocity / 200))
            c = GLOW[nt.pitch % len(GLOW)]
            active = abs(rel) < nt.duration
            d.ellipse([x - r, y - r, x + r, y + r],
                      fill=c if active else tuple(int(v * 0.35) for v in c),
                      outline=(255, 255, 255) if active else None,
                      width=2 if active else 0)
    # playhead line
    d.line([(int(w*0.92), int(h*0.06)), (int(w*0.92), int(h*0.60))],
           fill=(255, 255, 255), width=3)
    f_t = _font(0, int(w * 0.05))
    d.text((int(w*0.06), int(h*0.06)), "beatviz", font=f_t, fill=(240, 240, 240))
    return img


LOOKS = {"beatbars": look_beatbars, "aura": look_aura, "melody": look_melody}
