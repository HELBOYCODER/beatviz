"""Look pack: renders the akira-style looks (transit map, grid, neon, etc).

Each look is a function(frame_ctx) -> PIL.Image
"""
import math
from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def _font(path_idx=0, size=40):
    try:
        return ImageFont.truetype(FONT_PATHS[path_idx], size)
    except Exception:
        return ImageFont.load_default()


LINE_COLORS = [
    (229, 72, 77), (62, 99, 221), (18, 165, 148), (247, 107, 21),
    (231, 165, 0), (103, 148, 54), (143, 143, 143), (190, 60, 190),
]


class Ctx:
    def __init__(self, w, h, t, energy, beat, midi, notes_window):
        self.w, self.h, self.t, self.energy, self.beat = w, h, t, energy, beat
        self.midi = midi
        self.notes_window = notes_window


# ---- look: transit map (akira's signature 1080x1920 look) ----
def look_transit(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (250, 250, 248))
    d = ImageDraw.Draw(img)
    pad = int(w * 0.07)
    lanes = 7
    step = (h - 2 * pad - int(h * 0.22)) / lanes
    for i in range(lanes):
        col = LINE_COLORS[i % len(LINE_COLORS)]
        y = pad + i * step
        # orthogonal metro line with 45 deg jogs
        pts = [(pad, y)]
        x = pad
        seg = (w - 2 * pad) / 4
        for k in range(4):
            if (i + k) % 2 == 0:
                x2 = x + seg
                pts.append((x2, y))
                if k < 3:
                    diag = step * 0.45
                    pts.append((x2 + diag, y + diag))
                    x = x2 + diag
                    y += diag
            else:
                x2 = x + seg
                pts.append((x2, y))
                x = x2
        # energy pulse width
        lw = max(6, int(w * 0.012 * (1 + ctx.energy)))
        d.line(pts, fill=col, width=lw, joint="curve")
        # stations
        for j, (sx, sy) in enumerate(pts):
            r = int(w * 0.011) + (int(w * 0.006) if (j + int(ctx.t * 4)) % 5 == 0 else 0)
            if (i + j) % 3 == 0:
                d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(250, 250, 248), outline=col, width=max(3, lw // 3))
            else:
                d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=col)
    # beat flash frame
    if ctx.beat > 0.5:
        d.rectangle([0, 0, w - 1, h - 1], outline=(20, 20, 20), width=int(w * 0.012))
    # footer metadata (mono)
    f_t = _font(0, int(w * 0.062))
    f_m = _font(1, int(w * 0.021))
    fy = h - int(h * 0.155)
    d.text((pad, fy), "beat", font=f_t, fill=(20, 20, 20))
    meta = [
        f"Operator: beatviz · Lines: {lanes} in service",
        f"Tempo: {getattr(ctx.midi, 'bpm', 120) if ctx.midi else 120:.0f} BPM · Loudness: -{(18-ctx.energy*10):.1f} LUFS",
        f"Frame {ctx.t:05.2f}s · 1080x1920",
    ]
    for i, line in enumerate(meta):
        d.text((pad, fy + int(h * 0.075) + i * int(h * 0.028)), line, font=f_m, fill=(90, 90, 90))
    return img


# ---- look: neon bars ----
def look_bars(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 8, 18))
    d = ImageDraw.Draw(img)
    n = 40
    bw = w / n
    for i in range(n):
        e = ctx.energy * (0.5 + 0.5 * math.sin(ctx.t * 5 + i * 0.8))
        e *= 0.4 + 0.6 * abs(math.sin(i * 0.9 + ctx.t * 2))
        bh = int(h * 0.6 * max(0.02, e))
        c = LINE_COLORS[i % len(LINE_COLORS)]
        x = int(i * bw)
        d.rounded_rectangle([x + 4, h - bh, x + bw - 4, h], radius=int(bw / 3), fill=c)
    return img


# ---- look: piano roll from MIDI ----
def look_piano(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (12, 10, 24))
    d = ImageDraw.Draw(img)
    if not ctx.midi:
        return look_bars(ctx)
    lo, hi = ctx.midi.pitch_range()
    span = max(1, hi - lo)
    win = 6.0
    for nt in ctx.midi.notes:
        rel = nt.start - ctx.t
        if rel > win or rel < -nt.duration:
            continue
        x = int(w - (rel / win) * w)
        y = int(h * 0.05 + (1 - (nt.pitch - lo) / span) * h * 0.9)
        dur = max(10, int(nt.duration / win * w))
        r = max(5, int(h * 0.0035))
        c = LINE_COLORS[nt.pitch % len(LINE_COLORS)]
        d.rounded_rectangle([x - dur, y, x, y + r * 2], radius=r,
                            fill=c if abs(rel) < nt.duration else tuple(int(v * 0.4) for v in c))
    d.line([(w - 8, 0), (w - 8, h)], fill=(255, 255, 255), width=5)
    return img


# ---- look: radial MIDI burst ----
def look_radial(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 6, 16))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    r0 = int(min(w, h) * (0.1 + 0.12 * ctx.energy + 0.18 * ctx.beat))
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=LINE_COLORS[0])
    if ctx.midi:
        lo, hi = ctx.midi.pitch_range()
        span = max(1, hi - lo)
        for nt in ctx.midi.notes:
            age = ctx.t - nt.start
            if age < 0 or age > 2.0:
                continue
            f = age / 2.0
            r = r0 + int(f * min(w, h) * 0.42)
            ang = (nt.pitch - lo) / span * math.pi * 2
            x = cx + r * math.cos(ang)
            y = cy + r * math.sin(ang)
            rr = max(3, int(w * 0.012 * (1 - f)))
            c = LINE_COLORS[nt.pitch % len(LINE_COLORS)]
            fade = tuple(int(v * (1 - f)) for v in c)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fade)
    return img


# ---- look: waveform ----
def look_wave(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 10, 22))
    d = ImageDraw.Draw(img)
    mid = h // 2
    n = 120
    top, bot = [], []
    for i in range(n + 1):
        x = int(i / n * w)
        a = (abs(math.sin(i * 0.6 + ctx.t * 6)) * 0.7 + 0.1) * ctx.energy
        a += 0.06
        top.append((x, mid - int(a * h * 0.35)))
        bot.append((x, mid + int(a * h * 0.35)))
    d.polygon(top + list(reversed(bot)), fill=LINE_COLORS[2])
    d.line([(0, mid), (w, mid)], fill=(255, 255, 255), width=2)
    return img


LOOKS = {
    "transit": look_transit,
    "bars": look_bars,
    "piano": look_piano,
    "radial": look_radial,
    "wave": look_wave,
}
