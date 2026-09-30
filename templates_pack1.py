"""Template pack 1: 25 distinct music-visualizer looks (t01..t25) for beatviz.

Style: akira.center — minimal, high-contrast, editable gradient palettes,
designed for 9:16 vertical (1080x1920). Each look is fn(ctx) -> PIL.Image.
All looks degrade gracefully without MIDI and use real FFT spectrum data.

بستهٔ قالب ۱: ۲۵ قالب متمایز ویژوالایزر موسیقی برای beatviz.
هر قالب یک تابع fn(ctx) -> PIL.Image است با پالت گرادیانی قابل ویرایش.
"""
import math
from PIL import Image, ImageDraw

try:
    from looks_music import (gradient_color, spectrum_at, _font, LINE_COLORS,
                             GLOW)
except ImportError:
    from .looks_music import (gradient_color, spectrum_at, _font, LINE_COLORS,
                              GLOW)

# ---- editable gradient palettes (c0 -> c1 -> c2) ----
P_TEAL = ((0, 245, 212), (60, 99, 221), (170, 60, 220))       # cyan->blue->purple
P_SUNSET = ((255, 94, 98), (255, 175, 40), (255, 230, 0))     # red->amber->yellow
P_ICE = ((240, 250, 255), (120, 190, 255), (30, 70, 160))     # white->ice->deep blue
P_EMBER = ((255, 60, 0), (230, 30, 90), (60, 10, 60))         # fire
P_MINT = ((18, 165, 148), (180, 255, 160), (250, 250, 240))   # mint->cream
P_MONO = ((250, 250, 248), (160, 160, 165), (30, 30, 34))     # monochrome
BG_DARK = (10, 10, 16)
BG_DARK2 = (12, 12, 20)
BG_LIGHT = (250, 250, 248)


def _pal(f, pal):
    return gradient_color(f, *pal)


def _smooth(e):
    return max(0.02, e) ** 0.8


# ============================== t01 ==============================
def t01_spectrum_classic(ctx):
    """طیف‌نمای کلاسیک میله‌ای با گرادیان فیروزه‌ای | Classic full-width spectrum bars, teal gradient."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK)
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=48)
    base_y, max_h = int(h * 0.72), int(h * 0.44)
    bw = w / len(spec)
    gap = max(2, int(bw * 0.24))
    for i, e in enumerate(spec):
        bh = int(max_h * _smooth(e))
        col = _pal(i / (len(spec) - 1), P_TEAL)
        x = int(i * bw)
        d.rounded_rectangle([x + gap, base_y - bh, x + bw - gap, base_y],
                            radius=int(bw * 0.2), fill=col)
        r = int(bh * 0.30)
        d.rounded_rectangle([x + gap, base_y + int(h * 0.012),
                             x + bw - gap, base_y + int(h * 0.012) + r],
                            radius=int(bw * 0.2),
                            fill=tuple(int(c * 0.22) for c in col))
    lw = max(2, int(w * 0.002))
    d.line([(0, base_y), (w, base_y)],
           fill=tuple(min(255, int(c * (1 + ctx.beat))) for c in P_TEAL[0]),
           width=lw)
    return img


# ============================== t02 ==============================
def t02_mirror_bars(ctx):
    """میله‌های آینه‌ای از مرکز | Center-mirrored bars radiating vertically from midline."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK2)
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=32)
    mid, max_h = h // 2, int(h * 0.34)
    bw = w / len(spec)
    gap = max(2, int(bw * 0.26))
    for i, e in enumerate(spec):
        bh = int(max_h * _smooth(e))
        col = _pal(i / (len(spec) - 1), P_SUNSET)
        x0, x1 = int(i * bw) + gap, int((i + 1) * bw) - gap
        d.rounded_rectangle([x0, mid - bh, x1, mid + bh], radius=int(bw * 0.18),
                            fill=col)
    d.line([(0, mid), (w, mid)],
           fill=(240, 240, 240) if ctx.beat > 0.4 else (70, 70, 80), width=3)
    return img


# ============================== t03 ==============================
def t03_spectrum_ring(ctx):
    """حلقهٔ طیفی دایره‌ای | Circular spectrum: radial bars around a pulsing core."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK)
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=64)
    n = len(spec)
    r0 = min(w, h) * (0.16 + 0.03 * ctx.beat)
    rmax = min(w, h) * 0.24
    for i, e in enumerate(spec):
        ang = 2 * math.pi * i / n - math.pi / 2
        L = r0 + rmax * _smooth(e)
        col = _pal(i / n, P_TEAL)
        lw = max(3, int(w * 0.005))
        x0, y0 = cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)
        x1, y1 = cx + L * math.cos(ang), cy + L * math.sin(ang)
        d.line([(x0, y0), (x1, y1)], fill=col, width=lw)
    core = min(w, h) * (0.07 + 0.035 * ctx.beat)
    d.ellipse([cx - core, cy - core, cx + core, cy + core], fill=P_TEAL[0])
    return img


# ============================== t04 ==============================
def t04_sunburst(ctx):
    """تابش خورشیدی خطی | Radial sunburst spokes whose length tracks frequency bands."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (16, 10, 24))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.48)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=90)
    n = len(spec)
    for i, e in enumerate(spec):
        ang = 2 * math.pi * i / n - math.pi / 2
        L = min(w, h) * (0.10 + 0.34 * _smooth(e))
        col = _pal(i / n, P_SUNSET)
        lw = max(2, int(w * 0.0035))
        d.line([(cx, cy),
                (cx + L * math.cos(ang), cy + L * math.sin(ang))],
               fill=col, width=lw)
    r0 = min(w, h) * (0.045 + 0.03 * ctx.beat)
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=(255, 230, 0))
    return img


# ============================== t05 ==============================
def t05_wave_ribbon(ctx):
    """روبان موج واقعی صدا | Real waveform ribbon drawn from audio samples, beat-glowed."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK2)
    d = ImageDraw.Draw(img)
    mid = int(h * 0.48)
    n = 160
    c0 = int(ctx.t * ctx.sr)
    span = max(1, int(ctx.sr * 0.02))
    pts = []
    for i in range(n + 1):
        idx = min(len(ctx.mono) - 1, c0 + int(i / n * span) - span // 2)
        a = abs(ctx.mono[idx]) / 32768.0
        x = int(i / n * w)
        pts.append((x, mid - int(a * h * 0.28) - 2, mid + int(a * h * 0.28) + 2))
    for i, (x, y0, y1) in enumerate(pts):
        col = _pal(i / n, P_ICE)
        d.line([(x, y0), (x, y1)], fill=col,
               width=max(3, int(w * 0.004 * (1 + ctx.beat))))
    d.line([(0, mid), (w, mid)], fill=(60, 60, 75), width=2)
    return img


# ============================== t06 ==============================
def t06_oscilloscope(ctx):
    """اکسیلوسکوپ با شبکهٔ سبز فسفری | Phosphor oscilloscope trace on a dim grid."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 14, 8))
    d = ImageDraw.Draw(img)
    for gx in range(0, w, w // 8):
        d.line([(gx, 0), (gx, h)], fill=(14, 40, 20), width=1)
    for gy in range(0, h, w // 8):
        d.line([(0, gy), (w, gy)], fill=(14, 40, 20), width=1)
    mid = int(h * 0.46)
    c0 = int(ctx.t * ctx.sr)
    span = max(1, int(ctx.sr * 0.03))
    pts = []
    n = 200
    for i in range(n + 1):
        idx = min(len(ctx.mono) - 1, c0 + int(i / n * span) - span // 2)
        a = ctx.mono[idx] / 32768.0
        pts.append((int(i / n * w), mid - int(a * h * 0.22)))
    glow = (120, 255, 140) if ctx.beat > 0.4 else (40, 220, 90)
    d.line(pts, fill=glow, width=max(3, int(w * 0.004)), joint="curve")
    f_m = _font(1, int(w * 0.022))
    d.text((int(w * 0.06), int(h * 0.90)),
           f"CH1  {ctx.t:05.2f}s  {(180 - ctx.energy * 60):.0f}mV/div",
           font=f_m, fill=(60, 160, 80))
    return img


# ============================== t07 ==============================
def t07_piano_fall(ctx):
    """نُت‌های پیانو در حال سقوط | Falling piano-roll notes toward a hit line."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (12, 11, 22))
    d = ImageDraw.Draw(img)
    lo, hi = (ctx.midi.pitch_range() if ctx.midi else (48, 84))
    span = max(1, hi - lo)
    hit = int(h * 0.78)
    win = 3.5
    if ctx.midi:
        for nt in ctx.midi.notes:
            rel = ctx.t - nt.start  # positive after onset
            if rel < -0.15 or rel > nt.duration + win:
                continue
            y = hit - (-rel / win) * hit * 0.92  # above line, falls down
            lane_w = (w * 0.72) / span
            x = w * 0.14 + (nt.pitch - lo) * lane_w
            rw = max(3, int(lane_w * 0.42))
            col = _pal((nt.pitch - lo) / span, P_TEAL)
            active = 0 <= rel < nt.duration
            r_h = max(rw, int(nt.duration / win * hit * 0.92)) if active else rw
            d.rounded_rectangle([x - rw, y - r_h, x + rw, y + rw],
                                radius=rw,
                                fill=col if active else tuple(int(v * 0.30) for v in col))
    d.line([(int(w * 0.10), hit), (int(w * 0.90), hit)],
           fill=(255, 255, 255) if ctx.beat > 0.4 else (90, 90, 110),
           width=max(4, int(w * 0.006)))
    return img


# ============================== t08 ==============================
def t08_note_marbles(ctx):
    """گوی‌های نُت شناور | MIDI notes as glowing marbles streaming right to left."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 12, 18))
    d = ImageDraw.Draw(img)
    lo, hi = (ctx.midi.pitch_range() if ctx.midi else (48, 84))
    span = max(1, hi - lo)
    win = 6.0
    if ctx.midi:
        for nt in ctx.midi.notes:
            rel = nt.start - ctx.t
            if rel > win or rel < -nt.duration:
                continue
            x = int(w * 0.94 - (rel / win) * w * 0.88)
            y = int(h * 0.12 + (1 - (nt.pitch - lo) / span) * h * 0.5)
            r = int(w * 0.013 * (0.7 + nt.velocity / 200))
            active = abs(rel) < nt.duration
            col = _pal((nt.pitch - lo) / span, P_SUNSET)
            if active:
                d.ellipse([x - r, y - r, x + r, y + r], fill=col,
                          outline=(255, 255, 255), width=2)
            else:
                rc = tuple(int(v * 0.28) for v in col)
                d.ellipse([x - r, y - r, x + r, y + r], fill=rc)
    d.line([(int(w * 0.94), int(h * 0.08)), (int(w * 0.94), int(h * 0.66))],
           fill=(255, 255, 255), width=3)
    return img


# ============================== t09 ==============================
def t09_aura_pulse(ctx):
    """حلقه‌های هالهٔ ضربان‌دار | Concentric aura rings expanding from a breathing core."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK)
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=20)
    for i, e in enumerate(spec):
        r = int(min(w, h) * (0.14 + i * 0.030) + _smooth(e) * min(w, h) * 0.05)
        col = _pal(i / len(spec), P_ICE)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col,
                  width=max(3, int(w * 0.005 * (0.5 + e))))
    r0 = int(min(w, h) * (0.06 + 0.05 * ctx.beat + 0.03 * ctx.energy))
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=P_ICE[1])
    return img


# ============================== t10 ==============================
def t10_particle_burst(ctx):
    """انفجار ذرات روی هر ضرب | Particle sparks bursting outward on every beat."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK2)
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    phase = (ctx.t * 1.6) % 1.0
    n_dots = 48
    base_r = min(w, h) * (0.10 + 0.06 * ctx.energy)
    for i in range(n_dots):
        ang = 2 * math.pi * i / n_dots + ctx.t * 0.4
        f = (phase + i / n_dots) % 1.0
        r = base_r + f * min(w, h) * (0.10 + 0.24 * ctx.energy + 0.18 * ctx.beat)
        sz = max(2, int(w * 0.008 * (1 - f)))
        col = _pal(f, P_SUNSET)
        c = tuple(int(v * (1 - f * 0.8)) for v in col)
        x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=c)
    r0 = min(w, h) * (0.06 + 0.04 * ctx.beat)
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=(255, 230, 0))
    return img


# ============================== t11 ==============================
def t11_dot_matrix(ctx):
    """ماتریس نقطه‌ای اکولایزر | LED dot-matrix equalizer, two vertical columns."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 8, 10))
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=14)
    cols = 2
    rows = 16
    cell = min(w * 0.09, h * 0.036)
    pitch_x, pitch_y = cell * 1.5, cell * 1.28
    grid_w = cols * pitch_x
    x0 = (w - grid_w) / 2 + pitch_x / 2
    y0 = h * 0.28
    for j, e in enumerate(spec):
        lit = int(_smooth(e) * rows + 0.5) + (1 if ctx.beat > 0.5 else 0)
        cx = x0 + (j % cols) * pitch_x + (j // cols) * pitch_x * 0.55
        for r in range(rows):
            cy = y0 + (rows - 1 - r) * pitch_y
            on = r < lit
            col = _pal(r / rows, P_MINT)
            rr = cell * (0.42 if on else 0.30)
            cc = col if on else (28, 30, 30)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=cc)
    return img


# ============================== t12 ==============================
def t12_spectrogram_scroll(ctx):
    """اسپکتروگرام در حال اسکرول | Scrolling spectrogram history, newest at right."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_DARK)
    d = ImageDraw.Draw(img)
    nb = 28
    win_s = 8.0
    col_w = w / 60.0
    for k in range(59, -1, -1):
        tt = ctx.t - k * (win_s / 60.0)
        if tt < 0:
            continue
        spec = spectrum_at(ctx.mono, ctx.sr, tt, nbands=nb)
        x = int(w - (k + 1) * col_w)
        bw = col_w / nb
        for i, e in enumerate(spec):
            v = e ** 0.75
            col = _pal(v, P_EMBER)
            y = int(h * 0.82 - v * h * 0.62)
            d.rectangle([x + i * bw, y, x + (i + 1) * bw, int(h * 0.82)], fill=col)
    d.line([(0, int(h * 0.82)), (w, int(h * 0.82))], fill=(240, 240, 240), width=2)
    return img


# ============================== t13 ==============================
def t13_city_skyline(ctx):
    """خط افق شهر از طیف صدا | City skyline built from spectrum bars with window lights."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (14, 12, 24))
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=26)
    base_y = int(h * 0.74)
    bw = w / len(spec)
    for i, e in enumerate(spec):
        bh = int(h * 0.42 * (0.15 + _smooth(e)))
        col = _pal(i / len(spec), P_TEAL)
        x = int(i * bw)
        d.rectangle([x + 2, base_y - bh, x + int(bw) - 2, base_y], fill=col)
        # lit windows
        for wy in range(base_y - bh + 10, base_y - 8, 14):
            for wx in range(x + 8, x + int(bw) - 8, 12):
                if ((wx // 12 + wy // 14 + int(ctx.t * 3)) % 7) < 2:
                    d.rectangle([wx, wy, wx + 4, wy + 5], fill=(255, 235, 120))
    d.rectangle([0, base_y, w, h], fill=(6, 6, 12))
    return img


# ============================== t14 ==============================
def t14_light_tunnel(ctx):
    """تونل نور پرسپکتیو | Perspective light tunnel racing toward the viewer."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (6, 6, 14))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    rings = 12
    z = (ctx.t * 1.4) % 1.0
    for k in range(rings):
        f = (k / rings + z) % 1.0
        r = min(w, h) * (0.03 + f ** 2.2 * 0.75)
        alpha = max(0.05, 1.0 - f)
        col = _pal(f, P_ICE)
        c = tuple(int(v * alpha * (0.6 + 0.4 * ctx.energy)) for v in col)
        d.rectangle([cx - r * 0.9, cy - r * 1.6, cx + r * 0.9, cy + r * 1.6],
                    outline=c, width=max(2, int(w * 0.006 * (1 - f))))
    r0 = min(w, h) * (0.02 + 0.02 * ctx.beat)
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=(240, 250, 255))
    return img


# ============================== t15 ==============================
def t15_spectrum_spiral(ctx):
    """مارپیچ طیفی | Logarithmic spiral whose radius follows the spectrum."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 8, 18))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=72)
    n = len(spec)
    turns = 3.2
    r_base = min(w, h) * 0.03
    prev = None
    for i, e in enumerate(spec):
        f = i / n
        ang = 2 * math.pi * turns * f - math.pi / 2 + ctx.t * 0.5
        r = r_base + f * min(w, h) * (0.30 + 0.10 * _smooth(e))
        pt = (cx + r * math.cos(ang), cy + r * math.sin(ang))
        if prev:
            lw = max(3, int(w * 0.003 + 6 * e))
            d.line([prev, pt], fill=_pal(f, P_SUNSET), width=lw)
        prev = pt
    r0 = min(w, h) * (0.035 + 0.025 * ctx.beat)
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=(255, 230, 0))
    return img


# ============================== t16 ==============================
def t16_heartbeat(ctx):
    """خط نبض قلب (ECG) | ECG heartbeat line that spikes on beats over a clean field."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_LIGHT)
    d = ImageDraw.Draw(img)
    mid = int(h * 0.46)
    n = 180
    pts = []
    for i in range(n + 1):
        x = int(i / n * w)
        phase = (i / n * 3 + ctx.t * 2.0) % 1.0
        a = 0.0
        if 0.40 < phase < 0.52:
            ph = (phase - 0.40) / 0.12
            a = math.sin(ph * math.pi) * (0.5 + ctx.beat * 0.8)
        pts.append((x, mid - int(a * h * 0.16)))
    d.line(pts, fill=(190, 30, 45),
           width=max(5, int(w * 0.008 * (1 + ctx.beat))), joint="curve")
    f_m = _font(1, int(w * 0.024))
    bpm = ctx.bpm or 120
    d.text((int(w * 0.06), int(h * 0.86)), f"{bpm:.0f} BPM",
           font=f_m, fill=(190, 30, 45))
    d.line([(int(w * 0.06), int(h * 0.90)), (int(w * 0.40), int(h * 0.90))],
           fill=(190, 30, 45), width=2)
    return img


# ============================== t17 ==============================
def t17_vu_columns(ctx):
    """ستون‌های VU متر عمودی | Vertical VU columns with peak-hold caps, light background."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_LIGHT)
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=2)
    bars = [min(1.0, ctx.energy + 0.12), min(1.0, spec[-1] * 0.6 + ctx.energy * 0.7)]
    bw = w * 0.16
    gap = w * 0.10
    x0 = (w - 2 * bw - gap) / 2
    top, bot = int(h * 0.24), int(h * 0.76)
    seg = (bot - top) / 20
    for j, e in enumerate(bars):
        x = x0 + j * (bw + gap)
        d.rounded_rectangle([x, top, x + bw, bot], radius=int(bw * 0.10),
                            fill=(228, 228, 230), outline=(40, 40, 44), width=3)
        lit = int(e * 20 + 0.5)
        for r in range(20):
            y1 = bot - (r + 1) * seg + 2
            col = P_MINT[0] if r > 16 else (_pal(r / 20, P_TEAL) if r > 2 else P_ICE[2])
            if r < lit:
                d.rounded_rectangle([x + 4, y1, x + bw - 4, y1 + seg - 4],
                                    radius=6, fill=col)
    return img


# ============================== t18 ==============================
def t18_warp_field(ctx):
    """پرش ستاره‌ای در فضا | Starfield warp accelerating on beats."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (4, 4, 10))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    speed = 0.10 + 0.55 * ctx.energy + 0.8 * ctx.beat
    n_stars = 70
    for i in range(n_stars):
        ang = (i * 2.399963) % (2 * math.pi)
        f = ((i / n_stars + ctx.t * speed) % 1.0)
        r = f ** 2.4 * min(w, h) * 0.85
        x, y = cx + r * math.cos(ang), cy + r * math.sin(ang) * 1.6
        x2, y2 = cx + (r + 6 + 60 * speed * f) * math.cos(ang), \
                 cy + (r + 6 + 60 * speed * f) * math.sin(ang) * 1.6
        col = _pal(f, P_ICE)
        c = tuple(int(v * (0.25 + 0.75 * f)) for v in col)
        d.line([(x, y), (x2, y2)], fill=c, width=max(1, int(1 + 3 * f)))
    return img


# ============================== t19 ==============================
def t19_hex_grid(ctx):
    """شبکهٔ شش‌ضلعی نورانی | Honeycomb grid whose cells light up with the spectrum."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (10, 10, 14))
    d = ImageDraw.Draw(img)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=24)
    cell_r = w * 0.055
    dx, dy = cell_r * 1.5, cell_r * math.sqrt(3)
    cols, rows = 12, 24
    x0, y0 = w * 0.06, h * 0.10
    k = 0
    for row in range(rows):
        for col in range(cols):
            cx = x0 + col * dx
            cy = y0 + row * dy + (dx / 2 if row % 2 else 0)
            f = (row / rows + col / cols + ctx.t * 0.15) % 1.0
            e = spec[k % len(spec)] * (0.35 + 0.65 * (1 - abs(f - 0.5) * 2))
            k += 1
            if e < 0.12:
                continue
            e = min(1.0, e)
            r = cell_r * 0.86
            pts = [(cx + r * math.cos(a + math.pi / 6),
                    cy + r * math.sin(a + math.pi / 6))
                   for a in [i * math.pi / 3 for i in range(6)]]
            c = _pal(e, P_TEAL)
            c = tuple(int(v * (0.25 + 0.75 * e)) for v in c)
            d.polygon(pts, fill=c)
    return img


# ============================== t20 ==============================
def t20_terrain_ridges(ctx):
    """سلسله‌کوه‌های موجی (جوی دیویژن) | Joy-Division style stacked waveform ridges."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (16, 16, 18))
    d = ImageDraw.Draw(img)
    lines = 14
    top = int(h * 0.20)
    step = int(h * 0.045)
    n = 90
    for L in range(lines):
        y_base = top + L * step
        pts = [(0, y_base)]
        for i in range(1, n + 1):
            x = int(i / n * w)
            ph = math.sin(i * 0.35 + ctx.t * 3 + L * 1.3)
            a = (abs(ph) ** 1.6) * ctx.energy * step * 1.5 + 2
            pts.append((x, y_base - int(a)))
        pts += [(w, h), (0, h)]
        d.polygon(pts, fill=(16, 16, 18))
        d.line(pts[:n + 1], fill=(238, 238, 235),
               width=max(2, int(w * 0.0022)))
    f_m = _font(1, int(w * 0.024))
    d.text((int(w * 0.06), int(h * 0.88)), "UNKNOWN PLEASURES",
           font=f_m, fill=(200, 200, 200))
    return img


# ============================== t21 ==============================
def t21_grid_pulse(ctx):
    """شبکهٔ شهری با تپش ضرب | Akira-style city grid: orthogonal lanes pulsing with energy."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG_LIGHT)
    d = ImageDraw.Draw(img)
    lanes = 6
    pad = int(w * 0.08)
    span = (h - 2 * pad - int(h * 0.18)) / (lanes - 1)
    for i in range(lanes):
        y = pad + i * span
        col = LINE_COLORS[i % len(LINE_COLORS)]
        lw = max(6, int(w * 0.011 * (0.8 + ctx.energy + ctx.beat * 0.8)))
        d.line([(pad, y), (w - pad, y)], fill=col, width=lw)
        n_st = 7
        for j in range(n_st):
            x = pad + j * (w - 2 * pad) / (n_st - 1)
            r = int(w * 0.012 * (1 + (0.6 if (j + int(ctx.t * 3)) % 4 == 0 else 0)))
            d.ellipse([x - r, y - r, x + r, y + r], fill=BG_LIGHT,
                      outline=col, width=max(3, lw // 3))
    if ctx.beat > 0.5:
        d.rectangle([0, 0, w - 1, h - 1], outline=(20, 20, 20),
                    width=int(w * 0.010))
    return img


# ============================== t22 ==============================
def t22_vinyl(ctx):
    """صفحهٔ وینیل چرخان با طیف | Spinning vinyl disc with a spectrum groove arc."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (12, 12, 14))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.42)
    R = min(w, h) * 0.32
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(20, 20, 22),
              outline=(60, 60, 66), width=3)
    for g in range(5):
        r = R * (0.45 + 0.11 * g)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(40, 40, 44), width=2)
    rot = ctx.t * 1.05
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=48)
    n = len(spec)
    for i, e in enumerate(spec):
        ang = 2 * math.pi * i / n + rot
        L = R * (0.50 + 0.44 * _smooth(e))
        col = _pal(e, P_SUNSET)
        x0, y0 = cx + R * 0.48 * math.cos(ang), cy + R * 0.48 * math.sin(ang)
        x1, y1 = cx + L * math.cos(ang), cy + L * math.sin(ang)
        d.line([(x0, y0), (x1, y1)], fill=col, width=max(3, int(w * 0.004)))
    rc = R * 0.16
    d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=P_TEAL[0])
    rc2 = rc * 0.30
    d.ellipse([cx - rc2, cy - rc2, cx + rc2, cy + rc2], fill=(12, 12, 14))
    # tonearm
    d.line([(cx + R * 1.15, cy - R * 1.05), (cx + R * 0.55, cy + R * 0.35)],
           fill=(200, 200, 205), width=6)
    return img


# ============================== t23 ==============================
def t23_liquid_blob(ctx):
    """حباب مایع موج‌دار | Liquid blob whose radius wobbles with frequency bands."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 10, 18))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, int(h * 0.46)
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=40)
    n = len(spec)
    base = min(w, h) * (0.24 + 0.03 * ctx.beat)
    pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n - math.pi / 2
        e = spec[i] ** 0.7
        wobble = math.sin(3 * ang + ctx.t * 2.2) * 0.04 + math.sin(5 * ang - ctx.t * 3.1) * 0.03
        r = base * (1 + wobble + e * 0.28)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang) * 1.15))
    fill = _pal(min(1.0, 0.3 + ctx.energy * 0.6), P_TEAL)
    d.polygon(pts, fill=fill)
    inner = [(cx + (px - cx) * 0.55, cy + (py - cy) * 0.55) for px, py in pts]
    d.polygon(inner, fill=(8, 10, 18))
    return img


# ============================== t24 ==============================
def t24_kinetic_bpm(ctx):
    """تایپوگرافی متحرک BPM | Kinetic typography: giant BPM counter pulsing on beats."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (12, 12, 12))
    d = ImageDraw.Draw(img)
    bpm = ctx.bpm or 120
    size = int(w * (0.30 + 0.06 * ctx.beat))
    f_big = _font(0, size)
    txt = f"{bpm:.0f}"
    bb = d.textbbox((0, 0), txt, font=f_big)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    col = tuple(int(c * (0.7 + 0.3 * ctx.beat)) for c in (250, 250, 248))
    d.text(((w - tw) / 2, h * 0.36 - th / 2), txt, font=f_big, fill=col)
    f_m = _font(1, int(w * 0.032))
    bb2 = d.textbbox((0, 0), "BPM", font=f_m)
    d.text(((w - (bb2[2] - bb2[0])) / 2, h * 0.36 + size * 0.42),
           "BPM", font=f_m, fill=(120, 120, 125))
    # energy meter ring
    prog = ctx.t / max(0.01, ctx.duration)
    d.line([(0, h - 6), (w * prog, h - 6)], fill=P_TEAL[0],
           width=max(4, int(w * 0.008)))
    return img


# ============================== t25 ==============================
def t25_minimal_hud(ctx):
    """قالب مینیمال با نوار طیف گوشه و HUD | Minimal HUD: corner spectrum strip + track info."""
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (11, 11, 15))
    d = ImageDraw.Draw(img)
    # big quiet field: thin centered crosshair
    d.line([(w * 0.10, h * 0.46), (w * 0.90, h * 0.46)], fill=(45, 45, 55), width=2)
    d.line([(w * 0.50, h * 0.18), (w * 0.50, h * 0.74)], fill=(45, 45, 55), width=2)
    # energy dot orbits the crosshair
    ang = ctx.t * 1.2
    orb = min(w, h) * (0.14 + 0.06 * ctx.energy)
    px, py = w * 0.50 + orb * math.cos(ang), h * 0.46 + orb * math.sin(ang)
    r = int(w * (0.014 + 0.016 * ctx.beat))
    d.ellipse([px - r, py - r, px + r, py + r], fill=P_TEAL[0])
    # corner spectrum strip
    spec = spectrum_at(ctx.mono, ctx.sr, ctx.t, nbands=36)
    base_y = int(h * 0.93)
    bw = w / len(spec)
    for i, e in enumerate(spec):
        bh = int(h * 0.055 * _smooth(e))
        d.rectangle([int(i * bw) + 1, base_y - bh, int((i + 1) * bw) - 1, base_y],
                    fill=_pal(i / len(spec), P_TEAL))
    f_t = _font(0, int(w * 0.045))
    f_m = _font(1, int(w * 0.020))
    d.text((int(w * 0.06), int(h * 0.055)), "beatviz", font=f_t, fill=(240, 240, 240))
    d.text((int(w * 0.06), int(h * 0.105)),
           f"{ctx.t:04.1f}s / {ctx.duration:04.1f}s · E{(ctx.energy * 100):02.0f}",
           font=f_m, fill=(150, 150, 160))
    return img


LOOKS = {f"t{i:02d}": fn for i, fn in enumerate([
    t01_spectrum_classic, t02_mirror_bars, t03_spectrum_ring, t04_sunburst,
    t05_wave_ribbon, t06_oscilloscope, t07_piano_fall, t08_note_marbles,
    t09_aura_pulse, t10_particle_burst, t11_dot_matrix, t12_spectrogram_scroll,
    t13_city_skyline, t14_light_tunnel, t15_spectrum_spiral, t16_heartbeat,
    t17_vu_columns, t18_warp_field, t19_hex_grid, t20_terrain_ridges,
    t21_grid_pulse, t22_vinyl, t23_liquid_blob, t24_kinetic_bpm,
    t25_minimal_hud,
], start=1)}
