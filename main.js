// BeatViz desktop shell: starts the Python backend, opens the app window.
const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PORT = 8765;
let win = null;

function startBackend() {
  const res = app.isPackaged ? process.resourcesPath : __dirname;
  const pyDir = path.join(res, 'backend_env');
  const bin = path.join(pyDir, 'bin', 'python');
  const server = path.join(res, 'app_server.py');
  // packaged layout: backend_env = bundled python venv, app files at resources root
  return spawn(bin, [server, String(PORT)], {
    cwd: res,
    stdio: 'inherit',
    env: { ...process.env, PATH: `${pyDir}/bin:${process.env.PATH}` },
  });
}

function waitForBackend(tries = 60) {
  return new Promise((resolve, reject) => {
    const tick = (n) => {
      const req = http.get(`http://127.0.0.1:${PORT}/api/looks`, (r) => { r.resume(); resolve(); });
      req.on('error', () => {
        if (n <= 0) return reject(new Error('backend did not start'));
        setTimeout(() => tick(n - 1), 500);
      });
    };
    tick(tries);
  });
}

app.whenReady().then(async () => {
  let backend = null;
  try { backend = startBackend(); } catch (e) { console.error(e); }
  try { await waitForBackend(); } catch (e) { console.error(e); }

  win = new BrowserWindow({
    width: 1440, height: 900,
    minWidth: 1100, minHeight: 700,
    backgroundColor: '#0d1117',
    title: 'BeatViz',
    webPreferences: { contextIsolation: true },
  });
  win.setMenuBarVisibility(false);
  win.loadURL(`http://127.0.0.1:${PORT}/`);

  app.on('before-quit', () => { if (backend) backend.kill(); });
  app.on('window-all-closed', () => app.quit());
});
