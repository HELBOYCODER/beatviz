"""Graph look family for beatviz — knowledge-graph style visualizers.

Nodes = frequency bands / beats clustered by position in the spectrum.
Edges = relationships between concurrent bands (energy similarity +
spectral flux). Force-directed layout, animated by the music:
node size = band energy, edge weight = spectral flux, color = frequency
cluster via gradient.

Looks: graph_forced, graph_neural, graph_constellation
"""
import math
from PIL import Image, ImageDraw

try:
    from looks_music import spectrum_at, gradient_color
except ImportError:
    from .looks_music import spectrum_at, gradient_color

GLOW = [(255, 94, 98), (0, 245, 212), (255, 230, 0), (170, 120, 255)]
BG = (10, 10, 18)


def _font(idx, size):
    paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
    try:
        from PIL import ImageFont
        return ImageFont.truetype(paths[idx], size)
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


PREV = {}


def _bands(mono, sr, t, key, n=18):
    """Spectrum bands + spectral flux vs previous frame."""
    spec = spectrum_at(mono, sr, t, nbands=n)
    prev = PREV.get(key)
    if prev is None or len(prev) != n:
        flux = [0.0] * n
    else:
        flux = [min(1.0, max(0.0, spec[i] - prev[i]) * 4.0) for i in range(n)]
    PREV[key] = spec
    return spec, flux


def _cluster_color(f, lift=1.45):
    """Frequency position -> gradient color (low=teal .. high=magenta), lifted."""
    c = gradient_color(f)
    return tuple(min(255, int(v * lift)) for v in c)


def _edge_exists(spec, i, j, flux, thresh=0.12):
    """Edge weight between bands i,j: similarity in energy & flux."""
    e_sim = 1.0 - abs(spec[i] - spec[j])
    f_mix = (flux[i] + flux[j]) / 2.0
    w = max(0.0, e_sim * 0.6 + f_mix * 0.6 - 0.35)
    return w if w > thresh else 0.0


def _force_layout(spec, flux, w, h, t, energy, k=1.0):
    """Animated force-directed layout (deterministic seeds, no random)."""
    n = len(spec)
    cx, cy = w / 2, h / 2
    rad = min(w, h) * 0.36
    pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n + math.sin(t * 0.7 + i) * 0.35
        r = rad * (0.45 + 0.55 * ((i % 5) / 4.0)) * k
        pts.append([cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.92])
    # build edges
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            wgt = _edge_exists(spec, i, j, flux)
            if wgt > 0:
                edges.append((i, j, wgt))
    # iterative relaxation: repel all, attract along edges
    for _ in range(3):
        for i in range(n):
            for j in range(i + 1, n):
                dx = pts[j][0] - pts[i][0]
                dy = pts[j][1] - pts[i][1]
                d2 = max(dx * dx + dy * dy, 40.0)
                f = (min(w, h) * 0.03) / d2 * min(w, h) * 0.03
                dd = math.sqrt(d2)
                fx, fy = dx / dd * f, dy / dd * f
                pts[i][0] -= fx; pts[i][1] -= fy
                pts[j][0] += fx; pts[j][1] += fy
        for (i, j, wgt) in edges:
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            dd = max(math.sqrt(dx * dx + dy * dy), 1.0)
            target = min(w, h) * (0.10 + 0.10 * (1 - wgt))
            f = (dd - target) * 0.08 * (0.4 + wgt)
            fx, fy = dx / dd * f, dy / dd * f
            pts[i][0] += fx; pts[i][1] += fy
            pts[j][0] -= fx; pts[j][1] -= fy
        # keep in bounds
        m = min(w, h) * 0.08
        for p in pts:
            p[0] = max(m, min(w - m, p[0]))
            p[1] = max(m, min(h - m, p[1]))
    return pts, edges


def _label(d, w, h, t, energy, bpm, duration):
    f_t = _font(0, int(w * 0.05))
    f_m = _font(1, int(w * 0.020))
    d.text((int(w * 0.06), int(h * 0.06)), "beatviz", font=f_t, fill=(245, 245, 248))
    d.text((int(w * 0.06), int(h * 0.115)),
           f"{bpm or 120:.0f} BPM · {t:04.1f}s / {duration:04.1f}s · E{int(energy * 100)}",
           font=f_m, fill=(160, 160, 170))


# ---- LOOK: graph_forced — classic force-directed graph, glowing nodes ----
def look_graph_forced(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    spec, flux = _bands(ctx.mono, ctx.sr, ctx.t, 'forced')
    ctx._prev_spec = spec
    pts, edges = _force_layout(spec, flux, w, h, ctx.t, ctx.energy)
    # edges: width = weight (spectral flux), alpha-ish dim color
    for (i, j, wgt) in edges:
        col = _cluster_color((i + j) / (2 * len(spec)))
        dim = tuple(min(255, int(c * (0.55 + 0.9 * wgt))) for c in col)
        d.line([tuple(pts[i]), tuple(pts[j])], fill=dim,
               width=max(1, int(min(w, h) * 0.004 * (0.4 + wgt))))
    # nodes: size = band energy, color = frequency cluster
    n = len(spec)
    rmax = min(w, h) * 0.045
    for i in range(n):
        e = spec[i] ** 0.85
        r = rmax * (0.28 + 0.82 * e)
        col = _cluster_color(i / (n - 1))
        if e < 0.25:
            col = tuple(min(255, int(40 + v * 1.4)) for v in col)  # keep quiet nodes visible
        pulse = 1.0 + 0.35 * ctx.beat * (1.0 - i / n)
        rr = r * pulse
        x, y = pts[i]
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col)
        if e > 0.55:  # halo on hot bands
            d.ellipse([x - rr * 1.6, y - rr * 1.6, x + rr * 1.6, y + rr * 1.6],
                      outline=tuple(min(255, c + 60) for c in col),
                      width=max(1, int(min(w, h) * 0.003)))
    _label(d, w, h, ctx.t, ctx.energy, getattr(ctx, "bpm", None), ctx.duration)
    return img


# ---- LOOK: graph_neural — layered neural-net look, edges glow on flux ----
def look_graph_neural(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (8, 9, 16))
    d = ImageDraw.Draw(img)
    spec, flux = _bands(ctx.mono, ctx.sr, ctx.t, 'neural', n=21)
    ctx._prev_spec2 = spec
    n = len(spec)
    layers = 5
    per = n // layers
    pad = w * 0.12
    colw = (w - 2 * pad) / (layers - 1)
    pts = []
    for L in range(layers):
        cnt = per if L < layers - 1 else n - per * (layers - 1)
        x = pad + L * colw
        spread = h * (0.62 + 0.06 * math.sin(ctx.t + L))
        for k in range(cnt):
            y = h / 2 - spread / 2 + spread * (k + 0.5) / cnt
            pts.append([x + math.sin(ctx.t * 1.3 + L * 2 + k) * w * 0.012, y])
    idx = 0
    layer_of = []
    for L in range(layers):
        cnt = per if L < layers - 1 else n - per * (layers - 1)
        for _ in range(cnt):
            layer_of.append(L)
            idx += 1
    # edges between consecutive layers: weight = combined energy*flux
    for i in range(n):
        for j in range(n):
            if layer_of[j] != layer_of[i] + 1:
                continue
            wgt = _edge_exists(spec, i, j, flux, thresh=0.18)
            if wgt <= 0:
                continue
            col = _cluster_color((i + j) / (2 * n))
            col = tuple(min(255, int(c * (0.8 + 1.2 * wgt))) for c in col)
            if flux[i] + flux[j] > 0.35:
                col = tuple(min(255, c + 100) for c in col)
            d.line([tuple(pts[i]), tuple(pts[j])], fill=col,
                   width=max(1, int(min(w, h) * 0.0025 * (0.5 + wgt * 2))))
    # nodes
    for i in range(n):
        e = spec[i] ** 0.85
        r = min(w, h) * 0.030 * (0.25 + 0.75 * e) * (1 + 0.3 * ctx.beat)
        col = _cluster_color(i / (n - 1))
        x, y = pts[i]
        d.ellipse([x - r, y - r, x + r, y + r], fill=col,
                  outline=(255, 255, 255) if e > 0.7 else None,
                  width=2 if e > 0.7 else 0)
    # signal pulse traveling along x with the beat
    px = pad + (ctx.t % 1.0) * (w - 2 * pad)
    d.line([(px, h * 0.14), (px, h * 0.86)], fill=(0, 245, 212),
           width=max(1, int(h * 0.002)))
    _label(d, w, h, ctx.t, ctx.energy, getattr(ctx, "bpm", None), ctx.duration)
    return img


# ---- LOOK: graph_constellation — star map, nodes drift, edges faint ----
def look_graph_constellation(ctx):
    w, h = ctx.w, ctx.h
    img = Image.new("RGB", (w, h), (5, 6, 12))
    d = ImageDraw.Draw(img)
    spec, flux = _bands(ctx.mono, ctx.sr, ctx.t, 'constellation', n=24)
    ctx._prev_spec3 = spec
    n = len(spec)
    cx, cy = w / 2, h * 0.48
    rad = min(w, h) * 0.40
    pts = []
    for i in range(n):
        # slow orbital drift, seeded per node
        a0 = 2 * math.pi * hash01(i, 7) if False else 2 * math.pi * i / n
        ang = a0 + ctx.t * 0.25 * (1 if i % 2 else -1) + math.sin(ctx.t * 0.5 + i * 2) * 0.12
        r = rad * (0.35 + 0.65 * (i / n)) * (1.0 + 0.08 * math.sin(ctx.t + i))
        pts.append([cx + math.cos(ang) * r, cy + math.sin(ang) * r * 1.05])
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            wgt = _edge_exists(spec, i, j, flux, thresh=0.15)
            if wgt > 0:
                edges.append((i, j, wgt))
    for (i, j, wgt) in edges:
        col = _cluster_color((i + j) / (2 * n))
        dim = tuple(min(255, int(c * (0.30 + 0.85 * wgt))) for c in col)
        d.line([tuple(pts[i]), tuple(pts[j])], fill=dim,
               width=max(1, int(min(w, h) * 0.002 * (0.5 + wgt * 1.5))))
    for i in range(n):
        e = spec[i] ** 0.85
        r = min(w, h) * 0.006 + min(w, h) * 0.028 * e * (1 + 0.5 * ctx.beat)
        col = _cluster_color(i / (n - 1))
        x, y = pts[i]
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(min(255, c + 40) for c in col))
        # 4-point star sparkle on strong bands
        if e > 0.5:
            s = r * 3
            d.line([(x - s, y), (x + s, y)], fill=col, width=1)
            d.line([(x, y - s), (x, y + s)], fill=col, width=1)
    # center core beats with energy
    r0 = min(w, h) * (0.03 + 0.03 * ctx.energy + 0.02 * ctx.beat)
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=GLOW[1])
    _label(d, w, h, ctx.t, ctx.energy, getattr(ctx, "bpm", None), ctx.duration)
    return img


def hash01(a, b):
    hh = (a * 374761393 + b * 668265263) & 0xFFFFFFFF
    hh = ((hh ^ (hh >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((hh ^ (hh >> 16)) & 0xFFFFFFFF) / 4294967296.0


LOOKS = {
    "graph_forced": look_graph_forced,
    "graph_neural": look_graph_neural,
    "graph_constellation": look_graph_constellation,
}
