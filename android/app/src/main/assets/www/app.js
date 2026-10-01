/* BeatViz Android app logic: audio picking, preview render loop,
   MediaRecorder video export with offline playback rate. */

const $ = s => document.querySelector(s);
const cv = $('#cv'), d2 = cv.getContext('2d');
let audioFileUri = null, audioName = '', look = 'beatbars', audioEl = new Audio();
let audioCtx = null, analyser = null, srcNode = null, freqData = null, timeData = null;
let recording = false, rafId = null;

const isAndroid = !!(window.BeatVizAndroid && window.BeatVizAndroid.isAndroid && window.BeatVizAndroid.isAndroid());

// ---- look list ----
const lookIds = Object.keys(LOOKS);
$('#count').textContent = lookIds.length + ' قالب';
lookIds.forEach(id => {
  const o = document.createElement('option');
  o.value = id; o.textContent = `${id} — ${LOOKS[id].desc}`;
  $('#lookSel').appendChild(o);
});
$('#lookSel').onchange = e => { look = e.target.value; };

// ---- file picking ----
$('#pick').onclick = () => {
  if (isAndroid && window.BeatVizAndroid.pickAudio) window.BeatVizAndroid.pickAudio();
  else $('#file').click();
};
const fileInput = document.createElement('input');
fileInput.type = 'file'; fileInput.accept = 'audio/*';
fileInput.onchange = () => {
  if (!fileInput.files[0]) return;
  audioFileUri = URL.createObjectURL(fileInput.files[0]);
  audioName = fileInput.files[0].name;
  startPreview();
};
document.body.appendChild(fileInput);
fileInput.style.display = 'none';

window.__onAudioPicked = function(uri){
  audioFileUri = uri;
  audioName = decodeURIComponent((uri.split('/').pop() || 'audio')).split('?')[0];
  startPreview();
};

async function startPreview(){
  $('#status').textContent = '⏳ در حال تحلیل آهنگ…';
  if (isAndroid && window.BeatVizAndroid.readBase64){
    const b64 = window.BeatVizAndroid.readBase64(audioFileUri);
    audioEl.src = 'data:audio/mpeg;base64,' + b64;
  } else {
    audioEl.src = audioFileUri;
  }
  audioEl.loop = false;
  audioEl.addEventListener('error', () => {
    $('#status').textContent = '❌ خطا در بارگذاری آهنگ';
  });
  if (!audioCtx){
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    srcNode = audioCtx.createMediaElementSource(audioEl);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.72;
    srcNode.connect(analyser);
    analyser.connect(audioCtx.destination);
    freqData = new Uint8Array(analyser.frequencyBinCount);
    timeData = new Uint8Array(analyser.fftSize);
  }
  await audioCtx.resume();
  await new Promise(res => {
    if (audioEl.readyState >= 2) return res();
    audioEl.oncanplay = res;
  });
  $('#go').disabled = false;
  $('#status').textContent = '✓ ' + audioName + ' — آماده';
  // idle preview loop (render first frame look with silence)
  startLoop(false);
}

// ---- analysis context passed to looks ----
function makeCtx(t, duration, w, h){
  analyser.getByteFrequencyData(freqData);
  analyser.getByteTimeDomainData(timeData);
  const sr = audioCtx.sampleRate;
  let energy = 0;
  for (let i = 0; i < 32; i++) energy += freqData[i];
  energy = Math.min(1, energy/32/255 * 1.4);
  // beat: bass energy rising edge
  let bass = 0;
  for (let i = 0; i < 12; i++) bass += freqData[i];
  bass /= 12*255;
  const beat = Math.max(0, (bass - 0.55)) * 2.2;
  return {
    w, h, t, duration, energy,
    beat: Math.min(1, beat),
    bass,
    spec: (nbands) => spectrumBands(analyser, freqData, nbands, sr),
    timeDomain: () => timeData,
  };
}

function drawFrame(t, duration, w, h, targetCtx){
  const ctx = makeCtx(t, duration, w, h);
  const d = targetCtx || d2;
  LOOKS[look].fn(d, ctx);
}

// ---- preview loop on visible canvas ----
function sizeCanvas(){
  const r = cv.parentElement.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  cv.width = r.width * dpr;
  cv.height = r.height * dpr;
}
window.addEventListener('resize', sizeCanvas);

function startLoop(play){
  sizeCanvas();
  const w = cv.width, h = cv.height;
  const dur = +$('#dur').value || 15;
  if (play) audioEl.currentTime = 0, audioEl.play();
  const t0 = performance.now();
  cancelAnimationFrame(rafId);
  function frame(){
    const t = recording ? audioEl.currentTime
      : (play ? audioEl.currentTime : ((performance.now()-t0)/1000) % 10);
    if (play && !recording && (audioEl.ended || audioEl.paused && audioEl.currentTime > 0)){
      // loop preview
      audioEl.currentTime = 0; audioEl.play();
    }
    drawFrame(Math.min(t, dur), dur, w, h);
    if (recording && t >= dur){ finishRecording(); return; }
    rafId = requestAnimationFrame(frame);
  }
  frame();
}

// ---- video export via MediaRecorder on an offscreen canvas ----
let recorder = null, chunks = [];
function finishRecording(){
  recording = false;
  try { recorder.stop(); } catch(e){}
  audioEl.pause();
}

$('#go').onclick = async () => {
  if (!audioFileUri) return;
  $('#go').disabled = true;
  $('#prog').style.display = 'block';
  $('#prog > div').style.width = '5%';
  $('#status').textContent = '🎬 در حال ساخت ویدیو…';

  const W = Math.min(1080, +$('#w').value || 1080);
  const H = Math.min(1920, +$('#h').value || 1920);
  const dur = Math.min(120, +$('#dur').value || 15);

  const off = document.createElement('canvas');
  off.width = W; off.height = H;
  const od = off.getContext('2d');

  const stream = off.captureStream(30);
  // add audio track from a MediaElementSource into MediaStreamDestination
  const dest = audioCtx.createMediaStreamDestination();
  srcNode.disconnect();
  srcNode.connect(dest);
  srcNode.connect(analyser);
  dest.stream.getAudioTracks().forEach(t => stream.addTrack(t));

  let mime = 'video/webm;codecs=vp8,opus';
  if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm';
  chunks = [];
  recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6_000_000 });
  recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = () => {
    $('#prog > div').style.width = '100%';
    $('#status').textContent = '💾 در حال ذخیره…';
    const blob = new Blob(chunks, { type: 'video/webm' });
    saveBlob(blob);
  };

  const reader = new FileReader();
  // Play audio and render frames in real time
  audioEl.currentTime = 0;
  await audioCtx.resume();
  recorder.start(500);
  recording = true;

  const t0 = performance.now();
  let lastProg = 0;
  function rframe(){
    const t = audioEl.currentTime;
    drawFrame(Math.min(t, dur), dur, W, H, od);
    const p = Math.min(99, Math.round(t/dur*100));
    if (p > lastProg){ lastProg = p; $('#prog > div').style.width = p + '%'; }
    if (recording) requestAnimationFrame(rframe);
  }
  audioEl.play();
  requestAnimationFrame(rframe);
};

function saveBlob(blob){
  const name = 'beatviz_' + (look || 'look') + '_' + Date.now() + '.webm';
  if (isAndroid && window.BeatVizAndroid.saveBase64File){
    const r = new FileReader();
    r.onload = () => {
      const b64 = r.result.split(',')[1];
      const ok = window.BeatVizAndroid.saveBase64File(name, 'video/webm', b64);
      $('#status').textContent = ok
        ? '✅ ذخیره شد: Downloads/BeatViz/' + name
        : '❌ خطا در ذخیره';
      $('#go').disabled = false;
      setTimeout(() => { $('#prog').style.display = 'none'; $('#prog > div').style.width = '0%'; }, 1500);
    };
    r.readAsDataURL(blob);
  } else {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    $('#status').textContent = '✅ دانلود شد';
    $('#go').disabled = false;
  }
}
