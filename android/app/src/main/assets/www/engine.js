/* BeatViz JS engine — port of looks_music.py / looks.py / templates_pack1&2 (subset).
   Canvas 2D reimplementation of the PIL drawing code. */

// ---------- palettes & constants ----------
const P_TEAL = [[0,245,212],[60,99,221],[170,60,220]];
const P_SUNSET = [[255,94,98],[255,175,40],[255,230,0]];
const P_ICE = [[240,250,255],[120,190,255],[30,70,160]];
const P_EMBER = [[255,60,0],[230,30,90],[60,10,60]];
const P_MINT = [[18,165,148],[180,255,160],[250,250,240]];
const P_MONO = [[250,250,248],[160,160,165],[30,30,34]];
const BG_DARK = 'rgb(10,10,16)', BG_DARK2 = 'rgb(12,12,20)', BG_LIGHT = 'rgb(250,250,248)';
const LINE_COLORS = [
  [229,72,77],[62,99,221],[18,165,148],[247,107,21],
  [231,165,0],[103,148,54],[143,143,143],[190,60,190]];
const GLOW = [[255,94,98],[0,245,212],[255,230,0],[170,120,255]];

function lerp(a,b,f){ return a+(b-a)*f; }
function _lerp(a,b,f){ return Math.round(a+(b-a)*f); }
function gradientColor(f, c0, c1, c2){
  if (f < 0.5){
    const g = f*2;
    return `rgb(${_lerp(c0[0],c1[0],g)},${_lerp(c0[1],c1[1],g)},${_lerp(c0[2],c1[2],g)})`;
  }
  const g = (f-0.5)*2;
  return `rgb(${_lerp(c1[0],c2[0],g)},${_lerp(c1[1],c2[1],g)},${_lerp(c1[2],c2[2],g)})`;
}
function pal(f, p){ return gradientColor(f, p[0], p[1], p[2]); }
function rgba(c, a){ return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }
function dimC(c, m){ return `rgb(${Math.round(c[0]*m)},${Math.round(c[1]*m)},${Math.round(c[2]*m)})`; }
function smooth(e){ return Math.pow(Math.max(0.02, e), 0.8); }
function hash01(a, b){ // deterministic pseudo-random 0..1
  let h = (a|0) * 374761393 + (b|0) * 668265263;
  h = (h ^ (h >>> 13)) >>> 0;
  h = (h * 1274126177) >>> 0;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
function valueNoise(x, y){
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = x - xi, yf = y - yi;
  const u = xf*xf*(3-2*xf), v = yf*yf*(3-2*yf);
  return lerp(lerp(hash01(xi,yi), hash01(xi+1,yi), u),
              lerp(hash01(xi,yi+1), hash01(xi+1,yi+1), u), v);
}

// ---------- drawing helpers (PIL -> canvas) ----------
function roundedRect(d, x1, y1, x2, y2, r, fill, stroke, lw){
  const x = Math.min(x1,x2), y = Math.min(y1,y2);
  const w = Math.abs(x2-x1), h = Math.abs(y2-y1);
  r = Math.min(r, w/2, h/2);
  d.beginPath();
  d.moveTo(x+r, y);
  d.arcTo(x+w, y, x+w, y+h, r);
  d.arcTo(x+w, y+h, x, y+h, r);
  d.arcTo(x, y+h, x, y, r);
  d.arcTo(x, y, x+w, y, r);
  d.closePath();
  if (fill){ d.fillStyle = fill; d.fill(); }
  if (stroke){ d.strokeStyle = stroke; d.lineWidth = lw||2; d.stroke(); }
}

function beatvizLabel(d, ctx, small){
  const w = ctx.w, h = ctx.h;
  d.textAlign = 'left'; d.textBaseline = 'alphabetic';
  d.fillStyle = 'rgb(240,240,240)';
  d.font = `bold ${Math.round(w*0.045)}px sans-serif`;
  d.fillText('beatviz', w*0.06, h*0.085);
  d.fillStyle = 'rgb(150,150,160)';
  d.font = `${Math.round(w*0.02)}px monospace`;
  d.fillText(`${ctx.t.toFixed(1)}s / ${ctx.duration.toFixed(1)}s · E${Math.round(ctx.energy*100)}`,
    w*0.06, h*0.125);
}

// ---------- audio analysis ----------
function spectrumBands(analyser, freqData, nbands, sampleRate){
  // Web Audio FFT -> log-spaced normalized band magnitudes 40Hz..12kHz
  const fftSize = analyser.fftSize, half = fftSize/2;
  const fmin = 40, fmax = Math.min(12000, sampleRate/2);
  const out = [];
  for (let b = 0; b < nbands; b++){
    const f0 = fmin * Math.pow(fmax/fmin, b/nbands);
    const f1 = fmin * Math.pow(fmax/fmin, (b+1)/nbands);
    let i0 = Math.floor(f0/sampleRate * fftSize);
    let i1 = Math.max(Math.floor(f1/sampleRate * fftSize), i0+1);
    i0 = Math.min(Math.max(0,i0), half-1);
    i1 = Math.min(Math.max(i1, i0+1), half);
    let m = 0;
    for (let i = i0; i < i1; i++) m = Math.max(m, freqData[i]);
    out.push(m/255);
  }
  return out;
}

// ---------- LOOKS ----------
const LOOKS = {};

// beatbars — spectrum bars, mirror reflection, beat glow baseline
LOOKS['beatbars'] = { desc:'طیف ضربانی (اصلی)', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(12,12,20)'; d.fillRect(0,0,w,h);
  const spec = ctx.spec(40);
  const baseY = h*0.70, maxH = h*0.42, n = spec.length, bw = w/n, gap = Math.max(2, bw*0.22);
  for (let i = 0; i < n; i++){
    const e = Math.pow(spec[i], 0.8);
    const bh = maxH * e, x = i*bw;
    const c = gradientColor(i/(n-1), P_TEAL[0], P_TEAL[1], P_TEAL[2]);
    roundedRect(d, x+gap, baseY-bh, x+bw-gap, baseY, bw*0.18, c);
    roundedRect(d, x+gap, baseY+h*0.01, x+bw-gap, baseY+h*0.01+bh*0.35, bw*0.18, dimC(c.match(/\d+/g).map(Number), 0.25));
  }
  const glowA = 0.3 + 0.7*ctx.beat;
  d.strokeStyle = `rgba(0,245,212,${glowA})`;
  d.lineWidth = Math.max(2, h*0.002);
  d.beginPath(); d.moveTo(0, baseY); d.lineTo(w, baseY); d.stroke();
  beatvizLabel(d, ctx);
}};

// aura — concentric rings
LOOKS['aura'] = { desc:'حلقه‌های هاله', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(10,10,18)'; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h*0.48, spec = ctx.spec(24);
  const mn = Math.min(w,h);
  for (let i = 0; i < spec.length; i++){
    const e = Math.pow(spec[i], 0.9);
    const r = mn*0.12 + i*mn*0.028 + e*mn*0.05;
    d.strokeStyle = rgba(LINE_COLORS[i%8], 1);
    d.lineWidth = Math.max(3, w*0.006*(0.5+e));
    d.beginPath(); d.arc(cx, cy, r, 0, Math.PI*2); d.stroke();
  }
  const r0 = mn*(0.06 + 0.04*ctx.beat + 0.03*ctx.energy);
  d.fillStyle = rgba(GLOW[0],1);
  d.beginPath(); d.arc(cx, cy, r0, 0, Math.PI*2); d.fill();
  beatvizLabel(d, ctx);
}};

// bars — neon bars
LOOKS['bars'] = { desc:'میله‌های نئون', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(8,8,18)'; d.fillRect(0,0,w,h);
  const spec = ctx.spec(40), n = spec.length, bw = w/n;
  for (let i = 0; i < n; i++){
    const e = ctx.energy * (0.5 + 0.5*Math.sin(ctx.t*5 + i*0.8)) * (0.4 + 0.6*spec[i]);
    const bh = h*0.6*Math.max(0.02, e);
    roundedRect(d, i*bw+4, h-bh, (i+1)*bw-4, h, bw/3, rgba(LINE_COLORS[i%8],1));
  }
}};

// wave — waveform ribbon
LOOKS['wave'] = { desc:'موج صدا', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h, mid = h/2, n = 120;
  d.fillStyle = 'rgb(10,10,22)'; d.fillRect(0,0,w,h);
  const top = [], bot = [];
  const amp = ctx.wave || (() => 0.3);
  for (let i = 0; i <= n; i++){
    const x = i/n*w;
    const a = (Math.abs(Math.sin(i*0.6 + ctx.t*6))*0.7 + 0.1)*ctx.energy + 0.06;
    top.push([x, mid - a*h*0.35]);
    bot.push([x, mid + a*h*0.35]);
  }
  d.fillStyle = rgba(LINE_COLORS[2],1);
  d.beginPath(); d.moveTo(top[0][0], top[0][1]);
  top.forEach(p => d.lineTo(p[0], p[1]));
  bot.reverse().forEach(p => d.lineTo(p[0], p[1]));
  d.closePath(); d.fill();
  d.strokeStyle = '#fff'; d.lineWidth = 2;
  d.beginPath(); d.moveTo(0,mid); d.lineTo(w,mid); d.stroke();
}};

// t01 spectrum classic
LOOKS['t01_spectrum_classic'] = { desc:'طیف کلاسیک', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const spec = ctx.spec(48);
  const baseY = h*0.72, maxH = h*0.44, bw = w/spec.length, gap = Math.max(2, bw*0.24);
  for (let i = 0; i < spec.length; i++){
    const bh = maxH*smooth(spec[i]);
    const col = pal(i/(spec.length-1), P_TEAL);
    roundedRect(d, i*bw+gap, baseY-bh, (i+1)*bw-gap, baseY, bw*0.2, col);
    roundedRect(d, i*bw+gap, baseY+h*0.012, (i+1)*bw-gap, baseY+h*0.012+bh*0.30, bw*0.2, dimC(col.match(/\d+/g).map(Number), 0.22));
  }
  beatvizLabel(d, ctx);
}};

// t02 mirror bars
LOOKS['t02_mirror_bars'] = { desc:'طیف آینه‌ای', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK2; d.fillRect(0,0,w,h);
  const spec = ctx.spec(32), mid = h/2, bw = w/spec.length, gap = Math.max(2, bw*0.24);
  for (let i = 0; i < spec.length; i++){
    const bh = h*0.4*smooth(spec[i]);
    const col = pal(Math.abs(i - spec.length/2)/(spec.length/2), P_TEAL);
    roundedRect(d, i*bw+gap, mid-bh, (i+1)*bw-gap, mid, bw*0.2, col);
    roundedRect(d, i*bw+gap, mid, (i+1)*bw-gap, mid+bh*0.6, bw*0.2, dimC(col.match(/\d+/g).map(Number), 0.3));
  }
}};

// t03 spectrum ring
LOOKS['t03_spectrum_ring'] = { desc:'حلقهٔ طیفی', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2, spec = ctx.spec(56), mn = Math.min(w,h);
  const r0 = mn*0.18;
  for (let i = 0; i < spec.length; i++){
    const e = smooth(spec[i]);
    const ang = i/spec.length*Math.PI*2 - Math.PI/2;
    const r1 = r0 + e*mn*0.22;
    d.strokeStyle = pal(i/spec.length, P_TEAL);
    d.lineWidth = Math.max(2, w*0.008);
    d.beginPath();
    d.moveTo(cx + Math.cos(ang)*r0, cy + Math.sin(ang)*r0);
    d.lineTo(cx + Math.cos(ang)*r1, cy + Math.sin(ang)*r1);
    d.stroke();
  }
  const core = r0*(0.8 + 0.3*ctx.beat);
  d.fillStyle = rgba(GLOW[1], 0.9);
  d.beginPath(); d.arc(cx, cy, core, 0, Math.PI*2); d.fill();
}};

// t04 sunburst
LOOKS['t04_sunburst'] = { desc:'تابش خورشیدی', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h*0.52, spec = ctx.spec(72), mn = Math.min(w,h);
  for (let i = 0; i < spec.length; i++){
    const e = smooth(spec[i]);
    const ang = i/spec.length*Math.PI*2 - Math.PI/2;
    const r0 = mn*0.10, r1 = r0 + e*mn*0.38;
    d.strokeStyle = pal(i/spec.length, P_SUNSET);
    d.lineWidth = Math.max(1.5, w*0.006);
    d.beginPath();
    d.moveTo(cx + Math.cos(ang)*r0, cy + Math.sin(ang)*r0);
    d.lineTo(cx + Math.cos(ang)*r1, cy + Math.sin(ang)*r1);
    d.stroke();
  }
  d.fillStyle = rgba(GLOW[2], 0.8);
  d.beginPath(); d.arc(cx, cy, mn*(0.05 + 0.04*ctx.beat), 0, Math.PI*2); d.fill();
}};

// t05 wave ribbon (real waveform)
LOOKS['t05_wave_ribbon'] = { desc:'روبان موج', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const td = ctx.timeDomain(), n = td.length, mid = h/2;
  d.strokeStyle = pal(0.3, P_TEAL);
  d.lineWidth = Math.max(3, w*0.008);
  d.beginPath();
  for (let i = 0; i < n; i++){
    const x = i/(n-1)*w, y = mid + ((td[i]-128)/128)*h*0.35;
    i === 0 ? d.moveTo(x,y) : d.lineTo(x,y);
  }
  d.stroke();
  beatvizLabel(d, ctx);
}};

// t06 oscilloscope
LOOKS['t06_oscilloscope'] = { desc:'اکسیلوسکوپ', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(4,12,6)'; d.fillRect(0,0,w,h);
  d.strokeStyle = 'rgba(20,80,30,0.5)'; d.lineWidth = 1;
  const gs = w/16;
  for (let x = 0; x <= w; x += gs){ d.beginPath(); d.moveTo(x,0); d.lineTo(x,h); d.stroke(); }
  for (let y = 0; y <= h; y += gs){ d.beginPath(); d.moveTo(0,y); d.lineTo(w,y); d.stroke(); }
  const td = ctx.timeDomain(), n = td.length, mid = h/2;
  d.strokeStyle = '#39ff6a'; d.lineWidth = Math.max(3, w*0.006);
  d.shadowColor = '#39ff6a'; d.shadowBlur = w*0.01;
  d.beginPath();
  for (let i = 0; i < n; i++){
    const x = i/(n-1)*w, y = mid + ((td[i]-128)/128)*h*0.4;
    i === 0 ? d.moveTo(x,y) : d.lineTo(x,y);
  }
  d.stroke();
  d.shadowBlur = 0;
}};

// t09 aura pulse
LOOKS['t09_aura_pulse'] = { desc:'تپش هاله', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h, mn = Math.min(w,h);
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2, spec = ctx.spec(8);
  for (let i = 0; i < 8; i++){
    const e = spec[i];
    const r = mn*(0.08 + i*0.06 + e*0.08 + ctx.beat*0.04);
    d.strokeStyle = pal(i/8, P_TEAL);
    d.lineWidth = Math.max(2, w*0.01*(0.4+e));
    d.beginPath(); d.arc(cx, cy, r, 0, Math.PI*2); d.stroke();
  }
  d.fillStyle = rgba(GLOW[1], 0.9);
  d.beginPath(); d.arc(cx, cy, mn*(0.05+0.05*ctx.beat), 0, Math.PI*2); d.fill();
}};

// t10 particle burst
LOOKS['t10_particle_burst'] = { desc:'انفجار ذرات', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2, N = 200;
  for (let i = 0; i < N; i++){
    const seed = i*7.13;
    const ang = hash01(i, 1)*Math.PI*2;
    const speed = 0.3 + hash01(i,2)*0.7;
    const life = ((ctx.t*speed + hash01(i,3)) % 1);
    const r = life * Math.min(w,h) * (0.2 + 0.35*ctx.energy + 0.15*ctx.beat) * speed;
    const x = cx + Math.cos(ang)*r, y = cy + Math.sin(ang)*r;
    const sz = Math.max(1.5, w*0.005*(1-life));
    d.fillStyle = pal(hash01(i,4), P_TEAL);
    d.globalAlpha = 1 - life;
    d.beginPath(); d.arc(x, y, sz, 0, Math.PI*2); d.fill();
  }
  d.globalAlpha = 1;
  d.fillStyle = rgba(GLOW[1], 0.5 + 0.5*ctx.beat);
  d.beginPath(); d.arc(cx, cy, Math.min(w,h)*(0.03+0.04*ctx.beat), 0, Math.PI*2); d.fill();
}};

// t13 city skyline
LOOKS['t13_city_skyline'] = { desc:'خط افق شهر', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(6,6,14)'; d.fillRect(0,0,w,h);
  const spec = ctx.spec(24), baseY = h*0.88, bw = w/spec.length;
  for (let i = 0; i < spec.length; i++){
    const bh = h*0.5*Math.max(0.08, smooth(spec[i]));
    const x = i*bw;
    d.fillStyle = dimC(LINE_COLORS[i%8], 0.6);
    d.fillRect(x+2, baseY-bh, bw-4, bh);
    d.fillStyle = '#ffe08a';
    for (let wy = baseY-bh + bw*0.3; wy < baseY - bw*0.2; wy += bw*0.35){
      for (let wx = x + bw*0.2; wx < x+bw-bw*0.3; wx += bw*0.35){
        if (hash01(i*100 + Math.round(wx), Math.round(wy)) > 0.5 - 0.4*spec[i]){
          d.fillRect(wx, wy, bw*0.14, bw*0.14);
        }
      }
    }
  }
}};

// t15 spiral
LOOKS['t15_spectrum_spiral'] = { desc:'مارپیچ طیفی', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2, spec = ctx.spec(64), mn = Math.min(w,h);
  let r = mn*0.06, ang = ctx.t*0.5;
  for (let i = 0; i < spec.length; i++){
    const e = smooth(spec[i]);
    ang += 0.18 + e*0.1;
    r += mn*0.008;
    const x = cx + Math.cos(ang)*(r + e*mn*0.06);
    const y = cy + Math.sin(ang)*(r + e*mn*0.06);
    d.fillStyle = pal(i/spec.length, P_TEAL);
    d.beginPath(); d.arc(x, y, Math.max(2, w*0.01*(0.4+e)), 0, Math.PI*2); d.fill();
  }
}};

// t16 heartbeat ECG
LOOKS['t16_heartbeat'] = { desc:'خط نبض قلب', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(8,10,12)'; d.fillRect(0,0,w,h);
  const mid = h/2, n = 160, points = [];
  const phase = (ctx.t*2) % 1;
  for (let i = 0; i < n; i++){
    const x = i/n*w;
    const p = (i/n - phase + 1) % 1;
    let y = mid;
    if (p > 0.42 && p < 0.50) y = mid - Math.sin((p-0.42)/0.08*Math.PI)*h*0.22;
    else if (p >= 0.50 && p < 0.54) y = mid + h*0.10;
    else if (p >= 0.54 && p < 0.60) y = mid - h*0.05;
    else y = mid - Math.sin(p*Math.PI*4)*h*0.015;
    points.push([x, y]);
  }
  d.strokeStyle = '#ff4d6d'; d.lineWidth = Math.max(3, w*0.006);
  d.shadowColor = '#ff4d6d'; d.shadowBlur = w*0.012*(0.4+ctx.beat);
  d.beginPath();
  points.forEach((p,i) => i === 0 ? d.moveTo(p[0],p[1]) : d.lineTo(p[0],p[1]));
  d.stroke();
  d.shadowBlur = 0;
  beatvizLabel(d, ctx);
}};

// t17 VU columns
LOOKS['t17_vu_columns'] = { desc:'ستون‌های VU', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_LIGHT; d.fillRect(0,0,w,h);
  const spec = ctx.spec(12), n = spec.length, bw = w/(n*2);
  for (let i = 0; i < n; i++){
    const e = smooth(spec[i]);
    const segs = 20, x = i*2*bw + bw*0.2;
    const segH = h*0.75/segs, bot = h*0.9;
    for (let s = 0; s < segs; s++){
      const lit = s/segs < e;
      const col = s/segs > 0.8 ? '#ff4d4d' : s/segs > 0.6 ? '#ffcc4d' : '#4dff88';
      d.fillStyle = lit ? col : 'rgb(220,220,222)';
      d.fillRect(x, bot - (s+1)*segH + segH*0.15, bw*1.6, segH*0.7);
    }
  }
}};

// t19 hex grid
LOOKS['t19_hex_grid'] = { desc:'شبکهٔ شش‌ضلعی', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const spec = ctx.spec(16);
  const size = w/12, dx = size*1.5, dy = size*Math.sqrt(3);
  const cols = Math.ceil(w/dx)+1, rows = Math.ceil(h/dy)+1;
  for (let c = 0; c < cols; c++){
    for (let r = 0; r < rows; r++){
      const x = c*dx, y = r*dy + (c%2 ? dy/2 : 0);
      const bi = Math.floor(((c+rows-r)/(cols+rows)) * spec.length) % spec.length;
      const e = spec[bi];
      if (e < 0.12) continue;
      d.strokeStyle = pal(bi/spec.length, P_TEAL);
      d.globalAlpha = 0.2 + e*0.8;
      d.lineWidth = Math.max(1.5, size*0.06*(0.5+e));
      d.beginPath();
      for (let k = 0; k < 6; k++){
        const a = Math.PI/3*k;
        const px = x + Math.cos(a)*size*0.5, py = y + Math.sin(a)*size*0.5;
        k === 0 ? d.moveTo(px,py) : d.lineTo(px,py);
      }
      d.closePath(); d.stroke();
    }
  }
  d.globalAlpha = 1;
}};

// t21 grid pulse
LOOKS['t21_grid_pulse'] = { desc:'شبکهٔ شهری', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(8,10,18)'; d.fillRect(0,0,w,h);
  const spec = ctx.spec(10);
  const step = w/10;
  d.lineWidth = Math.max(1.5, w*0.003);
  for (let i = 0; i <= 10; i++){
    const p = i/10;
    d.strokeStyle = pal(p, P_TEAL);
    d.globalAlpha = 0.25 + spec[i % spec.length]*0.75;
    const off = Math.sin(ctx.t*2 + i)*w*0.01*ctx.energy;
    d.beginPath(); d.moveTo(i*step+off, 0); d.lineTo(i*step-off, h); d.stroke();
    d.beginPath(); d.moveTo(0, i*step); d.lineTo(w, i*step + off); d.stroke();
  }
  d.globalAlpha = 1;
}};

// t22 vinyl
LOOKS['t22_vinyl'] = { desc:'صفحهٔ وینیل', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h, mn = Math.min(w,h);
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2;
  const R = mn*0.35;
  d.fillStyle = '#111';
  d.beginPath(); d.arc(cx, cy, R, 0, Math.PI*2); d.fill();
  const spec = ctx.spec(24);
  const rot = ctx.t * (1.2 + ctx.energy*2);
  for (let g = 0; g < 14; g++){
    const r = R*(0.35 + g*0.045);
    d.strokeStyle = `rgba(80,80,90,${0.3 + spec[g % spec.length]*0.6})`;
    d.lineWidth = 2;
    d.beginPath(); d.arc(cx, cy, r, rot + g, rot + g + Math.PI*1.6); d.stroke();
  }
  d.fillStyle = rgba(GLOW[1], 0.9);
  d.beginPath(); d.arc(cx, cy, R*0.16*(1+0.3*ctx.beat), 0, Math.PI*2); d.fill();
  d.fillStyle = '#000';
  d.beginPath(); d.arc(cx, cy, R*0.02, 0, Math.PI*2); d.fill();
}};

// u04 terrain (simplified joy division ridges)
LOOKS['t20_terrain_ridges'] = { desc:'سلسله‌کوه‌های موجی', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = '#0a0a0e'; d.fillRect(0,0,w,h);
  const spec = ctx.spec(48);
  const rows = 14;
  for (let r = rows; r >= 1; r--){
    const y0 = h*0.25 + (rows-r)/rows*h*0.65;
    const amp = h*0.06*(1 - r/rows*0.5);
    d.fillStyle = '#0a0a0e';
    d.strokeStyle = 'rgba(240,240,255,0.85)';
    d.lineWidth = Math.max(1.5, w*0.002);
    d.beginPath();
    const pts = [];
    for (let i = 0; i <= 60; i++){
      const x = i/60*w;
      const n = valueNoise(i*0.15 + ctx.t*1.5, r*0.8);
      const bi = Math.floor(i/60*spec.length);
      const y = y0 - n*amp*(0.5 + spec[bi]*1.6);
      i === 0 ? d.moveTo(x,y) : d.lineTo(x,y);
      pts.push([x,y]);
    }
    d.stroke();
    d.lineTo(w, h); d.lineTo(0, h); d.closePath(); d.fill();
  }
}};

// u07 mandala petals (simplified)
LOOKS['t23_liquid_blob'] = { desc:'حباب مایع', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h, mn = Math.min(w,h);
  d.fillStyle = BG_DARK; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2, spec = ctx.spec(20);
  d.beginPath();
  for (let i = 0; i <= 60; i++){
    const a = i/60*Math.PI*2;
    const bi = spec[Math.floor(i/60*spec.length)];
    const wob = 1 + bi*0.5*Math.sin(a*6 + ctx.t*3) + ctx.beat*0.15;
    const r = mn*0.22*wob;
    const x = cx + Math.cos(a)*r, y = cy + Math.sin(a)*r;
    i === 0 ? d.moveTo(x,y) : d.lineTo(x,y);
  }
  d.closePath();
  const g = d.createLinearGradient(cx-mn*0.25, cy-mn*0.25, cx+mn*0.25, cy+mn*0.25);
  g.addColorStop(0, pal(0, P_TEAL)); g.addColorStop(1, pal(1, P_TEAL));
  d.fillStyle = g;
  d.globalAlpha = 0.85;
  d.fill();
  d.globalAlpha = 1;
}};

// u09 flow field (simplified particles)
LOOKS['t18_warp_field'] = { desc:'پرش ستاره‌ای', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(4,4,10)'; d.fillRect(0,0,w,h);
  const cx = w/2, cy = h/2, N = 140;
  const speed = 0.2 + ctx.energy*0.8 + ctx.beat*0.8;
  for (let i = 0; i < N; i++){
    const ang = hash01(i, 11)*Math.PI*2;
    const phase = (hash01(i, 12) + ctx.t*speed) % 1;
    const r = Math.pow(phase, 2)*Math.max(w,h)*0.7;
    const x0 = cx + Math.cos(ang)*r*0.3, y0 = cy + Math.sin(ang)*r*0.3;
    const x1 = cx + Math.cos(ang)*r, y1 = cy + Math.sin(ang)*r;
    d.strokeStyle = `rgba(255,255,255,${0.15 + phase*0.85})`;
    d.lineWidth = Math.max(1, phase*w*0.004);
    d.beginPath(); d.moveTo(x0, y0); d.lineTo(x1, y1); d.stroke();
  }
}};

// u21 solar system
LOOKS['t25_minimal_hud'] = { desc:'HUD مینیمال', fn: (d, ctx) => {
  const w = ctx.w, h = ctx.h;
  d.fillStyle = 'rgb(8,10,14)'; d.fillRect(0,0,w,h);
  const pad = w*0.06;
  // corner brackets
  d.strokeStyle = pal(0.2, P_TEAL); d.lineWidth = 3;
  const b = w*0.08;
  [[pad,pad,1,1],[w-pad,pad,-1,1],[pad,h-pad,1,-1],[w-pad,h-pad,-1,-1]].forEach(([x,y,sx,sy]) => {
    d.beginPath();
    d.moveTo(x+sx*b, y); d.lineTo(x, y); d.lineTo(x, y+sy*b);
    d.stroke();
  });
  // corner spectrum strip
  const spec = ctx.spec(24);
  const sy0 = h - pad*3, sx0 = pad + b*0.6;
  const bw = (w - 2*pad - b*0.6)/spec.length;
  for (let i = 0; i < spec.length; i++){
    const bh = h*0.12*smooth(spec[i]);
    d.fillStyle = pal(i/spec.length, P_TEAL);
    d.fillRect(sx0 + i*bw, sy0 - bh, bw*0.6, bh);
  }
  // center readout
  d.textAlign = 'left';
  d.fillStyle = 'rgb(240,240,240)';
  d.font = `bold ${Math.round(w*0.09)}px sans-serif`;
  d.fillText(`${Math.round(120 + ctx.energy*40)} BPM`, pad + b*0.6, h*0.42);
  d.fillStyle = 'rgb(150,150,160)';
  d.font = `${Math.round(w*0.025)}px monospace`;
  d.fillText(`BEATVIZ · ${ctx.t.toFixed(1)}s`, pad + b*0.6, h*0.47);
  d.strokeStyle = 'rgb(60,70,90)';
  roundedRect(d, pad + b*0.6, h*0.5, w - pad - b*0.3, h*0.508, 4, null, 'rgb(60,70,90)', 2);
  d.fillStyle = pal(0.1, P_TEAL);
  const prog = ctx.t/Math.max(0.01, ctx.duration);
  d.fillRect(pad + b*0.6, h*0.5, (w - 2*pad - b*0.9)*prog, h*0.008);
}};
