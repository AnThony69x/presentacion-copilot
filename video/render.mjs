// Renderiza intro.html a MP4: Chromium headless + CDP, captura cada fotograma con seek(t) y lo pasa a ffmpeg.
// Uso: node video/render.mjs [salida.mp4]        (video completo)
//      node video/render.mjs --stills 2,12,20     (PNGs sueltos en video/stills/ para revisar)
import {spawn} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';
import {homedir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const CHROME = process.env.CHROME || join(homedir(), '.cache/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-linux64/chrome-headless-shell');
const FPS = 30, PORT = 9333;
const args = process.argv.slice(2);
const stills = args[0] === '--stills' ? args[1].split(',').map(Number) : null;
const out = resolve(stills ? '' : args[0] || join(here, '..', 'copilot-outlook-intro.mp4'));

const chrome = spawn(CHROME, [`--remote-debugging-port=${PORT}`, '--window-size=1920,1080', '--hide-scrollbars',
  '--force-device-scale-factor=1', '--user-data-dir=/tmp/claude-1000/render-profile', 'about:blank'], {stdio: 'ignore'});
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find(t => t.type === 'page'); } catch {}
}
if (!target) { chrome.kill(); throw new Error('Chromium no arrancó: ' + CHROME); }

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((ok, ko) => {
  const i = ++id; pending.set(i, m => m.error ? ko(new Error(method + ': ' + m.error.message)) : ok(m.result));
  ws.send(JSON.stringify({id: i, method, params}));
});
const evalJS = async expr => {
  const r = await cdp('Runtime.evaluate', {expression: expr, awaitPromise: true, returnByValue: true});
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
};

await cdp('Emulation.setDeviceMetricsOverride', {width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false});
await cdp('Page.navigate', {url: 'file://' + join(here, 'intro.html') + '?render'});
await sleep(800);
await evalJS('document.fonts.ready.then(() => document.fonts.size)');
const DUR = await evalJS('DUR');
const shot = async t => { await evalJS(`seek(${t})`); return Buffer.from((await cdp('Page.captureScreenshot', {format: stills ? 'png' : 'jpeg', quality: stills ? undefined : 95})).data, 'base64'); };

if (stills) {
  mkdirSync(join(here, 'stills'), {recursive: true});
  for (const t of stills) writeFileSync(join(here, 'stills', `t${t}.png`), await shot(t));
  console.log('stills listos en', join(here, 'stills'));
} else {
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', FPS, '-c:v', 'mjpeg', '-i', '-',
    '-i', join(here, 'music.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '22', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], {stdio: ['pipe', 'inherit', 'inherit']});
  const N = Math.round(DUR * FPS);
  for (let f = 0; f < N; f++) {
    const buf = await shot(f / FPS);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 150 === 0) console.log(`fotograma ${f}/${N}`);
  }
  ff.stdin.end();
  await new Promise((ok, ko) => ff.on('close', c => c ? ko(new Error('ffmpeg salió con ' + c)) : ok()));
  console.log('video listo:', out);
}
ws.close(); chrome.kill();
