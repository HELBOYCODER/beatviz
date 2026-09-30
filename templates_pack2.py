"""beatviz template pack 2 — 25 experimental/pro looks (u01..u25).

Each template is fn(ctx) -> PIL.Image. ctx: .w .h .t .energy .beat .midi
.mono .sr .bpm .duration. Pure PIL, no numpy. Deterministic pseudo-random
via hash() so every render of the same frame is identical.
"""
import math
from PIL import Image, ImageDraw, ImageFont

try:
    from . import looks_music as LM
except ImportError:
    import looks_music as LM

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
NEON = [(255, 60, 100), (0, 245, 212), (255, 230, 0), (170, 120, 255),
        (60, 140, 255), (255, 140, 0)]


def _font(idx=0, size=40):
    try:
        return ImageFont.truetype(FONT_PATHS[idx], size)
    except Exception:
        return ImageFont.load_default()


def _hash01(*args):
    """Deterministic 0..1 pseudo-random from integer args."""
    h = 2166136261
    for a in args:
        h = ((h ^ (int(a) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    return ((h ^ (h >> 15)) & 0xFFFFFF) / 0x1000000


def _vnoise(x, y, seed=0):
    """Smooth-ish hash value noise (bilinear over integer lattice)."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    def g(i, j):
        return _hash01(i, j, seed)
    a = g(xi, yi)
    b = g(xi + 1, yi)
    c = g(xi, yi + 1)
    dd = g(xi + 1, yi + 1)
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + dd * u) * v


def _bands(ctx, n=32):
    return LM.spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=n)


def _bass(ctx):
    spec = _bands(ctx, 8)
    return sum(spec[:3]) / 3.0


# ---- u01: particle system — deterministic sparks drifting with audio ----
def u01_particles(ctx):
    """200 hash-seeded particles, size/velocity scaled by energy, burst on beat."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 6, 12))
    d = ImageDraw.Draw(img)
    n, speed = 220, 30 + 240 * ctx.energy
    for i in range(n):
        sx = _hash01(i, 1)
        sy = _hash01(i, 2)
        ph = _hash01(i, 3) * 6.283
        x = (sx * w + ctx.t * speed * (0.3 + _hash01(i, 4))) % w
        y = (sy * h + math.sin(ctx.t * 0.7 + ph) * h * 0.05) % h
        r = int(w * 0.003 * (1 + 4 * _hash01(i, 5)) * (0.5 + ctx.energy + ctx.beat))
        c = NEON[i % len(NEON)]
        fade = 0.35 + 0.65 * _hash01(i, 6)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=tuple(int(v * fade) for v in c))
    if ctx.beat > 0.5:
        r0 = int(min(w, h) * 0.3 * ctx.beat)
        d.ellipse([w/2 - r0, h/2 - r0, w/2 + r0, h/2 + r0],
                  outline=NEON[1], width=6)
    return img


# ---- u02: particle orbit trails — particles spiraling around center ----
def u02_orbit_trails(ctx):
    """Particles on decaying spiral orbits, trail = history of positions."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (4, 4, 10))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    n, R = 90, min(w, h) * 0.42
    for i in range(n):
        seed_a = _hash01(i, 7) * 6.283
        rate = 0.4 + 1.2 * _hash01(i, 8)
        decay = 0.5 + 0.5 * math.sin(ctx.t * rate + seed_a)
        pts = []
        for k in range(14):
            tt = ctx.t - k * 0.035
            r = R * (0.25 + 0.75 * abs(math.sin(tt * rate * 0.3 + seed_a)))
            r *= 0.7 + 0.5 * ctx.energy
            a = seed_a + tt * rate
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        col = NEON[i % len(NEON)]
        for k in range(len(pts) - 1):
            lw = max(1, int(w * 0.003 * (1 - k / 14) * (0.5 + decay)))
            d.line([pts[k], pts[k + 1]], fill=col, width=lw)
    return img


# ---- u03: tunnel/wormhole — perspective zoom of hashed rectangles ----
def u03_tunnel(ctx):
    """Nested rectangles rushing outward: wormhole zoom synced to energy."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (2, 2, 8))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    depth = 14
    zoom = (ctx.t * (0.35 + 1.1 * ctx.energy)) % 1.0
    for i in range(depth):
        f = ((i + zoom) / depth) ** 2.2  # far -> near
        s = 0.02 + f
        bw, bh = w * s * 2.6, h * s * 2.6
        rot = _hash01(i, 11) * 6.283
        k = 40
        pts = []
        for j in range(4):
            ang = rot + j * math.pi / 2
            px = cx + bw * math.cos(ang) * 0.707 + bw * 0.12 * math.sin(rot * 2 + j)
            py = cy + bh * math.sin(ang) * 0.707
            pts.append((px, py))
        fade = f
        col = tuple(int(v * fade) for v in NEON[i % len(NEON)])
        lw = max(1, int(w * 0.010 * f * (1 + ctx.beat)))
        d.line(pts + [pts[0]], fill=col, width=lw)
    r0 = int(min(w, h) * (0.04 + 0.05 * ctx.beat))
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=NEON[1])
    return img


# ---- u04: spectrum landscape — perspective grid mountains from FFT ----
def u04_terrain(ctx):
    """3D-ish spectrum terrain: rows of FFT history recede to a horizon."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 8, 20))
    d = ImageDraw.Draw(img)
    horizon = int(h * 0.32)
    rows, cols = 16, 40
    spec = _bands(ctx, cols)
    band_off = int(ctx.t * 2)
    for r in range(rows):  # far rows first
        persp = (r + 1) / rows
        y = horizon + int((h - horizon) * persp ** 1.7)
        pts = []
        for c in range(cols + 1):
            e = spec[(c + band_off) % cols] ** 1.2 * (1 - persp * 0.5)
            x = int(w / 2 + (c / cols - 0.5) * w * (0.25 + 0.75 * persp))
            pts.append((x, y - int(e * h * 0.16)))
        col = tuple(int(v * (0.25 + 0.75 * persp)) for v in NEON[1])
        d.line(pts, fill=col, width=max(2, int(w * 0.003 * persp)))
        if r % 4 == 0:
            d.line([(0, y), (w, y)], fill=(18, 18, 40), width=1)
    d.line([(0, horizon), (w, horizon)], fill=NEON[0], width=3)
    return img


# ---- u05: kaleidoscope — rotational symmetry of audio-reactive petals ----
def u05_kaleidoscope(ctx):
    """8-fold symmetric mirrored spectrum petals, rotating slowly."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (5, 5, 14))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    spec = _bands(ctx, 24)
    sym, rot = 8, ctx.t * 0.4
    R = min(w, h) * 0.46
    for s in range(sym):
        base = rot + s * 2 * math.pi / sym
        for i, e in enumerate(spec):
            e = e ** 1.1
            a0 = base + i * 0.045
            a1 = base + (i + 1) * 0.045
            r1 = R * (0.12 + 0.85 * e)
            col = LM.gradient_color(i / len(spec),
                                    (255, 60, 100), (255, 230, 0), (0, 245, 212))
            poly = [(cx, cy),
                    (cx + r1 * math.cos(a0), cy + r1 * math.sin(a0)),
                    (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1))]
            d.polygon(poly, fill=tuple(int(v * 0.75) for v in col))
    r0 = int(min(w, h) * (0.05 + 0.06 * ctx.beat))
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=(250, 250, 250))
    return img


# ---- u06: flow field — generative particles advected through hash noise ----
def u06_flow_field(ctx):
    """300 particles follow a perlin-ish flow field that swirls with energy."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 6, 12))
    d = ImageDraw.Draw(img)
    n = 300
    sc = 0.006 + 0.004 * math.sin(ctx.t * 0.2)
    for i in range(n):
        x0 = _hash01(i, 21) * w
        y0 = _hash01(i, 22) * h
        pts = [(x0, y0)]
        x, y = x0, y0
        for k in range(8):
            a = _vnoise(x * sc, y * sc, 7) * 6.283 * 2 * (1 + ctx.energy)
            x = (x + 14 * math.cos(a)) % w
            y = (y + 14 * math.sin(a)) % h
            pts.append((x, y))
        col = LM.gradient_color(_hash01(i, 23), (0, 245, 212), (170, 60, 220), (255, 90, 60))
        fade = 0.25 + 0.5 * ctx.energy
        d.line(pts, fill=tuple(int(v * fade) for v in col),
               width=max(1, int(w * 0.002)))
    return img


# ---- u07: 3D-ish waveform ribbon — stacked offset waveform slices ----
def u07_wave_ribbon(ctx):
    """Waveform ribbon with pseudo-3D depth: many slices offset by (x,y)."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 8, 18))
    d = ImageDraw.Draw(img)
    slices, mid = 14, h // 2
    for s in range(slices):  # back to front
        f = s / slices
        ph = ctx.t * 2.2 - f * 1.4
        amp = (h * 0.22) * (0.35 + 0.65 * ctx.energy) * (1 - f * 0.45)
        dx, dy = int(f * w * 0.10), int(f * h * 0.07)
        pts = []
        for i in range(101):
            x = i / 100 * (w - dx)
            a = (math.sin(i * 0.09 + ph) * 0.6 +
                 math.sin(i * 0.023 - ph * 1.7) * 0.4) * (0.3 + ctx.energy)
            pts.append((x + dx, mid + dy - int(a * amp)))
        col = tuple(int(v * (0.3 + 0.7 * (1 - f))) for v in NEON[s % len(NEON)])
        d.line(pts, fill=col, width=max(2, int(w * 0.004 * (1 - f) + 1)))
    return img


# ---- u08: city skyline equalizer — buildings whose windows flicker with FFT ----
def u08_skyline(ctx):
    """Neon city skyline; each building's height + window glow follow a band."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 10, 26))
    d = ImageDraw.Draw(img)
    spec = _bands(ctx, 22)
    n = len(spec)
    bw = w / n
    ground = int(h * 0.88)
    for i, e in enumerate(spec):
        e = e ** 0.9
        bh = int(h * 0.45 * max(0.08, e))
        x0, x1 = int(i * bw) + 2, int((i + 1) * bw) - 2
        col = tuple(int(v * (0.4 + 0.6 * e)) for v in (20, 24, 48))
        d.rectangle([x0, ground - bh, x1, h], fill=col)
        for wy in range(ground - bh + 8, h - 8, 14):   # windows
            for wx in range(x0 + 4, x1 - 4, 10):
                lit = _hash01(i, wx, wy) < e * 0.8
                if lit:
                    d.rectangle([wx, wy, wx + 4, wy + 6],
                                fill=NEON[(i + wy) % len(NEON)])
    d.line([(0, ground), (w, ground)], fill=NEON[1], width=4)
    return img


# ---- u09: vinyl record — spinning record, tonearm, grooves pulse on beat ----
def u09_vinyl(ctx):
    """Spinning vinyl with reactive grooves, label shows BPM."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (14, 12, 16))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.42)
    R = min(w, h) * 0.40
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(18, 18, 18))
    spin = ctx.t * (2.0 + 4.0 * ctx.energy)
    for g in range(16):
        rr = R * (0.30 + 0.70 * g / 16)
        shine = abs(math.sin(spin + g * 0.7))
        col = tuple(int(30 + 60 * shine * (0.4 + ctx.energy)) for _ in range(3))
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], 0, 360,
              fill=col, width=max(2, int(w * 0.003)))
    lab = R * 0.28
    d.ellipse([cx - lab, cy - lab, cx + lab, cy + lab], fill=NEON[0])
    f = _font(0, int(lab * 0.5))
    d.text((cx, cy), f"{(ctx.bpm or 120):.0f}", font=f, fill=(10, 10, 10), anchor="mm")
    # marker dot to show spin
    mr = R * 0.9
    mx, my = cx + mr * math.cos(spin), cy + mr * math.sin(spin)
    d.ellipse([mx - 8, my - 8, mx + 8, my + 8], fill=(250, 250, 250))
    # tonearm
    ax, ay = int(w * 0.82), int(h * 0.16)
    tx, ty = cx + R * 0.55 * math.cos(-0.9), cy + R * 0.55 * math.sin(-0.9)
    d.line([(ax, ay), (tx, ty)], fill=(200, 200, 205), width=int(w * 0.010))
    d.ellipse([ax - 14, ay - 14, ax + 14, ay + 14], fill=(120, 120, 130))
    return img


# ---- u10: cassette tape — two reels spinning, tape position follows time ----
def u10_cassette(ctx):
    """Retro cassette: reels spin with energy, tape spools shift with progress."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (18, 20, 24))
    d = ImageDraw.Draw(img)
    cw, ch = int(w * 0.86), int(h * 0.52)
    x0, y0 = (w - cw) // 2, (h - ch) // 2 - int(h * 0.05)
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=int(cw * 0.06),
                        fill=(40, 44, 52), outline=(90, 95, 105), width=4)
    prog = ctx.t / max(0.01, ctx.duration)
    rx1, rx2 = x0 + int(cw * 0.28), x0 + int(cw * 0.72)
    ry = y0 + int(ch * 0.42)
    spin = ctx.t * (3 + 8 * ctx.energy)
    for rx, frac in ((rx1, prog), (rx2, 1 - prog)):
        R = int(cw * (0.10 + 0.06 * frac))
        d.ellipse([rx - R, ry - R, rx + R, ry + R], fill=(15, 15, 18))
        for k in range(6):  # spokes to show spin
            a = spin + k * math.pi / 3
            d.line([(rx, ry), (rx + R * 0.85 * math.cos(a), ry + R * 0.85 * math.sin(a))],
                   fill=(150, 150, 160), width=3)
        d.ellipse([rx - 8, ry - 8, rx + 8, ry + 8], fill=(220, 220, 225))
    d.rectangle([x0 + int(cw*0.28), ry - 4, x0 + int(cw*0.72), ry + 4], fill=(30, 28, 26))
    f = _font(1, int(w * 0.028))
    d.text((x0 + cw * 0.5, y0 + ch * 0.78), f"{(ctx.bpm or 120):.0f} BPM  ·  SIDE A",
           font=f, fill=(200, 200, 205), anchor="mm")
    return img


# ---- u11: oscilloscope lissajous — X/Y curves morphing with spectrum ----
def u11_lissajous(ctx):
    """Lissajous curves; frequency ratio drifts with spectral centroid-ish."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (4, 8, 6))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    spec = _bands(ctx, 8)
    fr = 1 + sum(spec) * 2.5
    A = min(w, h) * 0.40 * (0.7 + 0.4 * ctx.energy)
    pts = []
    for i in range(361):
        th = i / 360 * 2 * math.pi
        x = cx + A * math.sin(th * max(1, round(fr)) + ctx.t)
        y = cy + A * math.sin(2 * th + ctx.t * 1.3)
        pts.append((x, y))
    glow = NEON[1] if ctx.beat < 0.5 else (255, 255, 255)
    d.line(pts + pts[:20], fill=glow, width=max(3, int(w * 0.006)))
    d.line(pts, fill=(0, 120, 90), width=2)
    return img


# ---- u12: starfield hyperspace — stars streak outward on beats ----
def u12_starfield(ctx):
    """Stars fly outward; speed jumps with energy, streaks stretch on beat."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (2, 2, 10))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    speed = 0.08 + 0.5 * ctx.energy + 1.2 * ctx.beat
    for i in range(160):
        a = _hash01(i, 31) * 2 * math.pi
        r0 = _hash01(i, 32)
        r = ((r0 + ctx.t * speed) % 1.0) ** 2.5 * max(w, h) * 0.75
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        x2, y2 = cx + (r + 10 + 90 * ctx.beat) * math.cos(a), cy + (r + 10 + 90 * ctx.beat) * math.sin(a)
        c = int(140 + 115 * (r / (max(w, h) * 0.75)))
        d.line([(x, y), (x2, y2)], fill=(c, c, min(255, c + 20)),
               width=max(1, int(w * 0.002 * (1 + r0))))
    return img


# ---- u13: plasma — classic color plasma, warped by audio ----
def u13_plasma(ctx):
    """Coarse-grid plasma with palette cycling, amplitude follows energy."""
    w, h = ctx.w, ctx.h
    step = max(8, w // 90)
    img = Image.new("RGB", (w // step + 1, h // step + 1))
    px = img.load()
    sc = 0.05 + 0.03 * ctx.energy
    tt = ctx.t * 1.5
    for gy in range(img.height):
        for gx in range(img.width):
            x, y = gx * step * sc, gy * step * sc
            v = (math.sin(x + tt) + math.sin(y + tt * 1.3) +
                 math.sin((x + y) * 0.7 + tt * 0.7) +
                 math.sin(math.hypot(x, y) * 0.8 - tt)) * 0.25
            f = (v + 1) / 2
            px[gx, gy] = LM.gradient_color(f, (20, 0, 60), (200, 40, 140), (255, 220, 120))
    return img.resize((w, h), Image.BILINEAR)


# ---- u14: barcode scan — vertical stripes reading spectrum, scanning beam ----
def u14_barcode(ctx):
    """Barcode whose stripe widths encode FFT bands; a scanline sweeps."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (250, 250, 250))
    d = ImageDraw.Draw(img)
    spec = _bands(ctx, 56)
    x = int(w * 0.10)
    for i, e in enumerate(spec):
        bw = max(2, int(w * (0.004 + 0.016 * e ** 0.8)))
        if i % 2 == 0:
            d.rectangle([x, int(h * 0.18), x + bw, int(h * 0.74)], fill=(10, 10, 10))
        x += bw + max(1, int(w * 0.003))
        if x > w * 0.92:
            break
    sy = int(h * (0.18 + 0.56 * ((ctx.t * 0.4) % 1.0)))
    d.line([(int(w*0.08), sy), (int(w*0.94), sy)], fill=(220, 40, 60), width=6)
    f = _font(1, int(w * 0.026))
    d.text((int(w*0.10), int(h*0.80)), f"SCAN {ctx.t:04.1f}s  ·  {(ctx.bpm or 120):.0f} BPM",
           font=f, fill=(60, 60, 60))
    return img


# ---- u15: holographic HUD — sci-fi interface reacting to audio ----
def u15_hologram_hud(ctx):
    """Holographic HUD: rings, ticks, waveform readout, corner brackets."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (3, 10, 12))
    d = ImageDraw.Draw(img)
    cyan = (0, 230, 220)
    cx, cy = w // 2, int(h * 0.40)
    for i in range(4):
        r = min(w, h) * (0.12 + 0.09 * i) * (1 + 0.05 * ctx.energy)
        a0 = ctx.t * (0.4 + 0.3 * i) * (1 if i % 2 else -1)
        d.arc([cx - r, cy - r, cx + r, cy + r], a0 * 57.3, a0 * 57.3 + 240,
              fill=cyan, width=max(2, int(w * 0.004)))
    spec = _bands(ctx, 48)
    for i, e in enumerate(spec):  # radial tick readout
        a = i / len(spec) * 2 * math.pi - math.pi / 2
        r1, r2 = min(w, h) * 0.50, min(w, h) * (0.50 + 0.12 * e ** 1.2)
        d.line([(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                (cx + r2 * math.cos(a), cy + r2 * math.sin(a))],
               fill=(0, 180, 175), width=2)
    f = _font(1, int(w * 0.03))
    d.text((int(w*0.07), int(h*0.07)), f"AUDIO LINK ▸ {(ctx.bpm or 120):.0f} BPM  PWR {ctx.energy:.2f}",
           font=f, fill=cyan)
    d.rectangle([int(w*0.05), int(h*0.05), w - int(w*0.05), h - int(h*0.12)],
                outline=(0, 120, 118), width=2)
    return img


# ---- u16: bass marbles — heavy balls drop and bounce on bass hits ----
def u16_bass_marbles(ctx):
    """Balls spawned on bass peaks fall with pseudo-physics (analytic bounce)."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 8, 16))
    d = ImageDraw.Draw(img)
    bass = _bass(ctx)
    ground = int(h * 0.86)
    d.line([(0, ground), (w, ground)], fill=(70, 70, 90), width=4)
    n = 18
    for i in range(n):
        birth = i * 0.9
        if ctx.t < birth:
            continue
        age = ctx.t - birth
        x = w * (0.08 + 0.84 * _hash01(i, 41))
        per = 1.1 + 0.4 * _hash01(i, 42)      # bounce period
        ph = (age / per) % 1.0
        amp = h * 0.5 * (0.5 + 0.5 * bass)
        y = ground - amp * abs(math.sin(ph * math.pi)) * (1 - ph * 0.15) if age < 40 else ground
        r = int(w * (0.018 + 0.020 * _hash01(i, 43)) * (1 + 0.3 * ctx.beat))
        col = NEON[i % len(NEON)]
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        d.ellipse([x - r*0.4 - r*0.2, y - r*0.5, x - r*0.2, y - r*0.3],
                  fill=(255, 255, 255))
    return img


# ---- u17: fireworks — rockets bloom on beats, deterministic sparks ----
def u17_fireworks(ctx):
    """Each beat fires a rocket; sparks expand and fade deterministically."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (4, 4, 12))
    d = ImageDraw.Draw(img)
    period = 1.2
    for k in range(int(ctx.t / period) + 1):
        birth = k * period + _hash01(k, 51) * 0.5
        age = ctx.t - birth
        if age < 0 or age > 1.6:
            continue
        cx = w * (0.15 + 0.70 * _hash01(k, 52))
        cy = h * (0.15 + 0.45 * _hash01(k, 53))
        col = NEON[k % len(NEON)]
        n_sp = 26
        rad = min(w, h) * 0.30 * (age / 1.6) ** 0.6
        for s in range(n_sp):
            a = s / n_sp * 2 * math.pi + _hash01(k, 54) * 6.28
            rr = rad * (0.7 + 0.3 * _hash01(k, s, 55))
            x, y = cx + rr * math.cos(a), cy + rr * math.sin(a) + rad * rad * 0.8
            fade = 1 - age / 1.6
            r = max(1, int(w * 0.004 * fade))
            d.ellipse([x - r, y - r, x + r, y + r],
                      fill=tuple(int(v * fade) for v in col))
    return img


# ---- u18: matrix rain — falling glyph columns, brightness = bands ----
def u18_matrix_rain(ctx):
    """Green code rain; column speed/brightness keyed to spectrum bands."""
    w, h = ctx.w, ctx.h
    cols_n = 34
    cw = w // cols_n
    img = Image.new("RGB", (w, h), (0, 8, 2))
    d = ImageDraw.Draw(img)
    spec = _bands(ctx, cols_n)
    f = _font(1, int(cw * 0.9))
    glyphs = "01アイウエオカキクケコｱｲｳｴｵ#$%&"
    for c in range(cols_n):
        e = spec[c % len(spec)]
        speed = (2 + 14 * e)
        head = (ctx.t * speed + _hash01(c, 61) * h * 2) % (h + 200) - 100
        for k in range(18):  # trail
            y = head - k * cw
            if y < -cw or y > h:
                continue
            g = glyphs[int(_hash01(c, k, int(ctx.t * 6))) % len(glyphs)]
            fade = max(0.0, 1 - k / 18) * (0.3 + 0.7 * e)
            col = (250, 255, 250) if k == 0 else (0, int(200 * fade) + 30, 20)
            d.text((c * cw + 2, y), g, font=f, fill=col)
    return img


# ---- u19: orbiting planets — sun + planets sized by frequency bands ----
def u19_planets(ctx):
    """Solar system: each planet's radius maps to a spectrum band, orbit speed too."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (4, 4, 14))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    spec = _bands(ctx, 6)
    R0 = min(w, h) * 0.06 * (1 + 0.3 * ctx.beat)
    d.ellipse([cx - R0, cy - R0, cx + R0, cy + R0], fill=(255, 200, 60))
    for i, e in enumerate(spec):
        orbit = min(w, h) * (0.13 + 0.075 * i)
        a = ctx.t * (0.5 + 0.4 * e) * (1 if i % 2 else -1) + i
        x, y = cx + orbit * math.cos(a), cy + orbit * 0.55 * math.sin(a)
        d.ellipse([cx - orbit, cy - orbit * 0.55, cx + orbit, cy + orbit * 0.55],
                  outline=(40, 40, 70), width=1)
        r = int(min(w, h) * (0.012 + 0.045 * e ** 0.8))
        col = NEON[i % len(NEON)]
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    return img


# ---- u20: phyllotaxis petals — sunflower spiral opens with melody/energy ----
def u20_phyllotaxis(ctx):
    """Golden-angle dot spiral; dots bloom outward scaled by energy & beat."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 6, 10))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    n = 320
    ga = math.pi * (3 - math.sqrt(5))
    spread = min(w, h) * (0.018 + 0.012 * ctx.energy + 0.02 * ctx.beat)
    open_f = 0.35 + 0.65 * min(1.0, ctx.t / 4) * (0.6 + 0.5 * ctx.energy)
    for i in range(n):
        a = i * ga + ctx.t * 0.25
        r = spread * math.sqrt(i) * open_f
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        if not (-r * 2 < x < w + r and 0 < y < h):
            continue
        s = max(1, int(w * 0.003 * (1 + 3 * _hash01(i, 71))))
        col = LM.gradient_color(i / n, (255, 90, 140), (255, 210, 90), (120, 220, 255))
        d.ellipse([x - s, y - s, x + s, y + s], fill=col)
    return img


# ---- u21: geometric mandala — bar-synced symmetric line mandala ----
def u21_mandala(ctx):
    """12-fold mandala; layer rotation quantized to musical bars via bpm."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 6, 16))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    bpm = ctx.bpm or 120
    bar = (ctx.t * bpm / 60 / 4) % 1.0
    snap = round(bar)  # rotates one step per bar
    spec = _bands(ctx, 12)
    for layer in range(5):
        sym = 6 + layer * 3
        rot = (snap + ctx.t * 0.1 * layer) * 2 * math.pi / sym
        R = min(w, h) * (0.14 + 0.08 * layer) * (1 + 0.15 * spec[layer % 12])
        pts = []
        for i in range(sym):
            a = rot + i * 2 * math.pi / sym
            rr = R * (0.8 + 0.3 * _hash01(layer, i, snap))
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        col = NEON[layer % len(NEON)]
        d.polygon(pts, outline=col, width=max(2, int(w * 0.004)))
        for (px, py) in pts:
            d.line([(cx, cy), (px, py)], fill=tuple(int(v * 0.4) for v in col), width=1)
    return img


# ---- u22: neon text ticker — filename/BPM marquee over spectrum ----
def u22_neon_ticker(ctx):
    """Giant scrolling neon text (title/bpm) over a floor of spectrum bars."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (5, 5, 12))
    d = ImageDraw.Draw(img)
    base_y = int(h * 0.80)
    spec = _bands(ctx, 36)
    bw = w / len(spec)
    for i, e in enumerate(spec):
        bh = int(h * 0.28 * (e ** 0.9))
        d.rectangle([int(i * bw) + 1, base_y - bh, int((i + 1) * bw) - 1, base_y],
                    fill=tuple(int(v * 0.5) for v in NEON[i % len(NEON)]))
    title = f"◆ {(ctx.bpm or 120):.0f} BPM ◆ BEATVIZ PACK2 ◆ "
    f = _font(0, int(w * 0.14))
    tw = d.textlength(title, font=f)
    x = int(w - ((ctx.t * w * 0.22) % (tw + w)))
    for k in range(max(2, int((w + tw) // tw) + 2)):
        xx = x + int(k * tw)
        if xx > w:
            break
        d.text((xx + 4, int(h * 0.30)), title, font=f, fill=(0, 80, 90))
        d.text((xx, int(h * 0.30)), title, font=f, fill=(0, 245, 212))
    return img


# ---- u23: 4-way split mosaic — four mini looks in one frame ----
def u23_mosaic(ctx):
    """Quad split: particles / rings / bars / waveform in four panes."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    hw, hh = w // 2, h // 2

    class Sub:  # lightweight sub-ctx with remapped origin
        pass
    for qx in (0, 1):
        for qy in (0, 1):
            sub = Sub()
            sub.w, sub.h = hw, hh
            sub.t = ctx.t + qx * 0.31 + qy * 0.17
            sub.energy, sub.beat = ctx.energy, ctx.beat
            sub.midi, sub.mono, sub.sr = ctx.midi, ctx.mono, ctx.sr
            sub.bpm, sub.duration = ctx.bpm, ctx.duration
            pane = {  # reuse simple in-pack renderers per quadrant
                (0, 0): u01_particles, (1, 0): u05_kaleidoscope,
                (0, 1): u08_skyline, (1, 1): u11_lissajous}[(qx, qy)](sub)
            img.paste(pane, (qx * hw, qy * hh))
    lw = max(4, w // 200)
    d.rectangle([hw - lw // 2, 0, hw + lw // 2, h], fill=(230, 230, 235))
    d.rectangle([0, hh - lw // 2, w, hh + lw // 2], fill=(230, 230, 235))
    return img


# ---- u24: heartbeat ECG — kick-triggered ECG trace with pulse glow ----
def u24_ecg(ctx):
    """ECG line: QRS spike fires on each beat, grid + BPM readout."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 10, 8))
    d = ImageDraw.Draw(img)
    mid = int(h * 0.45)
    for gx in range(0, w, w // 24):  # monitor grid
        d.line([(gx, 0), (gx, h)], fill=(12, 30, 24), width=1)
    for gy in range(0, h, h // 14):
        d.line([(0, gy), (w, gy)], fill=(12, 30, 24), width=1)
    bpm = ctx.bpm or 120
    beat_per = 60.0 / bpm
    pts = []
    for i in range(w // 4 + 1):
        tt = ctx.t - (w // 4 - i) * 0.004  # right-most is 'now'
        ph = (tt / beat_per) % 1.0
        y = 0.0
        if ph < 0.08:
            y = math.sin(ph / 0.08 * math.pi) * 0.15          # P wave
        elif ph < 0.12:
            y = -(ph - 0.08) / 0.04 * 0.9                     # Q dip
        elif ph < 0.16:
            y = -0.9 + (ph - 0.12) / 0.04 * 1.9               # R spike
        elif ph < 0.20:
            y = 1.0 - (ph - 0.16) / 0.04 * 1.3                # S drop
        elif ph < 0.40:
            y = math.sin((ph - 0.20) / 0.20 * math.pi) * 0.3  # T wave
        pts.append((i * 4, mid - int(y * h * (0.10 + 0.06 * ctx.energy))))
    col = (80, 255, 120) if ctx.beat < 0.4 else (220, 255, 225)
    d.line(pts, fill=col, width=max(3, int(w * 0.006)))
    f = _font(0, int(w * 0.07))
    d.text((int(w * 0.06), int(h * 0.80)), f"{bpm:.0f} BPM", font=f, fill=(80, 255, 120))
    return img


# ---- u25: chromatic grid warp — grid lines bend with spectrum (closer) ----
def u25_grid_warp(ctx):
    """Perspective floor+ceiling grid whose lines ripple with bass energy."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 4, 18))
    d = ImageDraw.Draw(img)
    horizon = h // 2
    bass = _bass(ctx)
    for i in range(1, 16):  # depth lines ripple toward viewer
        f = (i / 16 + (ctx.t * 0.25) % (1 / 16)) % 1.0
        y = horizon + int((h / 2) * f ** 2.0)
        wob = int(math.sin(f * 9 + ctx.t * 3) * w * 0.02 * (0.3 + bass))
        col = tuple(int(v * f) for v in NEON[1])
        d.line([(0 - wob, y), (w + wob, y)], fill=col, width=2)
    for k in range(-10, 11):  # radial lanes converge at horizon
        x_top = w / 2 + k * w * 0.02
        x_bot = w / 2 + k * w * 0.16
        d.line([(x_top, horizon), (x_bot, h)],
               fill=tuple(int(v * 0.6) for v in NEON[4]), width=2)
    d.line([(0, horizon), (w, horizon)], fill=(255, 255, 255),
           width=max(2, int(w * 0.004 * (1 + 2 * ctx.beat))))
    return img


LOOKS = {
    "u01_particles": u01_particles,
    "u02_orbit_trails": u02_orbit_trails,
    "u03_tunnel": u03_tunnel,
    "u04_terrain": u04_terrain,
    "u05_kaleidoscope": u05_kaleidoscope,
    "u06_flow_field": u06_flow_field,
    "u07_wave_ribbon": u07_wave_ribbon,
    "u08_skyline": u08_skyline,
    "u09_vinyl": u09_vinyl,
    "u10_cassette": u10_cassette,
    "u11_lissajous": u11_lissajous,
    "u12_starfield": u12_starfield,
    "u13_plasma": u13_plasma,
    "u14_barcode": u14_barcode,
    "u15_hologram_hud": u15_hologram_hud,
    "u16_bass_marbles": u16_bass_marbles,
    "u17_fireworks": u17_fireworks,
    "u18_matrix_rain": u18_matrix_rain,
    "u19_planets": u19_planets,
    "u20_phyllotaxis": u20_phyllotaxis,
    "u21_mandala": u21_mandala,
    "u22_neon_ticker": u22_neon_ticker,
    "u23_mosaic": u23_mosaic,
    "u24_ecg": u24_ecg,
    "u25_grid_warp": u25_grid_warp,
}
