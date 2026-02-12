#!/usr/bin/env python3
"""
VR Gyro Mouse — Maximum Performance Edition
pip install aiohttp pynput pyopenssl

Run: python server.py
Open iPhone Safari → https://<IP>:6000
Tap 'Advanced → Visit Website' to bypass SSL warning.
"""
import asyncio, json, os, socket, ssl, tempfile
from aiohttp import web, WSMsgType
from pynput.mouse import Button, Controller

PORT  = 6000
mouse = Controller()
DANGER=100

# ─────────────────────────────────────────────────────────────────────────────
def get_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:    s.connect(('8.8.8.8', 1)); return s.getsockname()[0]
        except: return '127.0.0.1'

def make_ssl_ctx():
    """Throwaway self-signed cert — iOS needs HTTPS for DeviceOrientation API."""
    try:
        from OpenSSL import crypto
    except ImportError:
        print("⚠  pip install pyopenssl  (needed for iOS HTTPS)")
        return None
    key = crypto.PKey(); key.generate_key(crypto.TYPE_RSA, 2048)
    c = crypto.X509()
    c.get_subject().CN = "vrmouse"
    c.set_serial_number(1)
    c.gmtime_adj_notBefore(0); c.gmtime_adj_notAfter(365 * 24 * 3600)
    c.set_issuer(c.get_subject()); c.set_pubkey(key); c.sign(key, 'sha256')
    cf = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
    kf = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
    cf.write(crypto.dump_certificate(crypto.FILETYPE_PEM, c)); cf.close()
    kf.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key)); kf.close()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cf.name, kf.name)
    os.unlink(cf.name); os.unlink(kf.name)
    return ctx

# ─────────────────────────────────────────────────────────────────────────────
IP   = get_ip()
SSL  = make_ssl_ctx()
SCHEME    = 'https' if SSL else 'http'
WS_SCHEME = 'wss'   if SSL else 'ws'

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>VR Mouse</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne+Mono&family=Syne:wght@700;800&display=swap');
:root {{
  --g:#c8ff00; --o:#ff6b00; --r:#ff3344;
  --bg:#090909; --dim:#1a1a1a;
  --fh:'Syne',sans-serif; --fm:'Syne Mono',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
html,body{{height:100%;overflow:hidden;background:var(--bg);color:#fff;font-family:var(--fm)}}
body{{display:flex;flex-direction:column;align-items:center;justify-content:space-between;
      padding:26px 20px 34px}}
/* scanlines */
body::before{{content:'';position:fixed;inset:0;z-index:99;pointer-events:none;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,
  rgba(255,255,255,.012) 3px,rgba(255,255,255,.012) 4px)}}

/* Header */
header{{text-align:center}}
h1{{font-family:var(--fh);font-size:24px;font-weight:800;letter-spacing:9px;
    color:var(--g);text-shadow:0 0 28px rgba(200,255,0,.5),0 0 60px rgba(200,255,0,.15)}}
.sub{{font-size:9px;letter-spacing:5px;color:#2a2a2a;margin-top:4px}}

/* Enable button */
#enableBtn{{
  background:transparent;border:1.5px solid var(--g);color:var(--g);
  font-family:var(--fh);font-weight:800;font-size:12px;letter-spacing:5px;
  padding:17px 38px;border-radius:3px;cursor:pointer;
  box-shadow:0 0 24px rgba(200,255,0,.08),inset 0 0 24px rgba(200,255,0,.03);
  text-shadow:0 0 10px rgba(200,255,0,.4);transition:all .15s;text-transform:uppercase
}}
#enableBtn:active{{background:rgba(200,255,0,.07);transform:scale(.97)}}
#enableBtn.live{{border-color:#282828;color:#282828;text-shadow:none;box-shadow:none;cursor:default}}

/* Status */
#status{{font-size:10px;letter-spacing:3px;color:#222;text-align:center;transition:color .3s;
         display:flex;align-items:center;gap:7px;justify-content:center}}
#status.on{{color:var(--g)}} #status.err{{color:var(--r)}}
.dot{{width:6px;height:6px;border-radius:50%;background:currentColor;flex-shrink:0}}
#status.on .dot{{box-shadow:0 0 8px var(--g)}}

/* Sliders */
.controls{{width:100%;display:flex;flex-direction:column;gap:12px}}
.srow{{display:flex;align-items:center;gap:10px}}
.slbl{{font-size:9px;letter-spacing:2px;color:#383838;width:58px;text-align:right;flex-shrink:0}}
.sval{{font-size:10px;color:var(--g);width:30px;text-align:left;flex-shrink:0}}
input[type=range]{{-webkit-appearance:none;flex:1;height:2px;background:#1e1e1e;border-radius:2px}}
input[type=range]::-webkit-slider-thumb{{
  -webkit-appearance:none;width:22px;height:22px;border-radius:50%;
  background:var(--g);box-shadow:0 0 10px rgba(200,255,0,.5)}}

/* Toggles */
.toggles{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}}
.tbtn{{
  background:transparent;border:1px solid #1e1e1e;color:#2e2e2e;
  font-family:var(--fm);font-size:9px;letter-spacing:2px;
  padding:8px 13px;border-radius:2px;cursor:pointer;transition:all .15s
}}
.tbtn.on{{border-color:var(--o);color:var(--o)}}

/* Mouse buttons */
.mbtns{{display:flex;gap:12px;width:100%}}
.mbtn{{flex:1;background:transparent;border:none;padding:0;border-radius:8px;
       cursor:pointer;overflow:hidden;-webkit-user-select:none;user-select:none}}
.minner{{padding:26px 8px;border-radius:8px;border:1.5px solid;
          font-family:var(--fh);font-weight:800;font-size:13px;letter-spacing:4px;
          transition:background .08s;text-transform:uppercase}}
#lbtn .minner{{border-color:var(--g);color:var(--g)}}
#rbtn .minner{{border-color:var(--o);color:var(--o)}}
#lbtn:active .minner{{background:rgba(200,255,0,.08)}}
#rbtn:active .minner{{background:rgba(255,107,0,.08)}}

/* Debug */
#dbg{{font-size:9px;color:#1a1a1a;letter-spacing:2px}}
#dbg.on{{color:#262626}}
</style>
</head>
<body>

<header>
  <h1>VR MOUSE</h1>
  <div class="sub">GYROSCOPE CONTROLLER</div>
</header>

<button id="enableBtn">⟁ ENABLE MOTION</button>

<div id="status"><span class="dot"></span>OPEN IN SAFARI · TAP TO ENABLE</div>

<div class="controls">
  <div class="srow">
    <span class="slbl">SENS</span>
    <input type="range" id="sensSlider" min="3" max="60" value="22">
    <span class="sval" id="sensVal">22</span>
  </div>
  <div class="srow">
    <span class="slbl">SMOOTH</span>
    <input type="range" id="emaSlider" min="10" max="95" value="55">
    <span class="sval" id="emaVal">.55</span>
  </div>
</div>

<div class="toggles">
  <button class="tbtn" id="tInvX">INVERT X</button>
  <button class="tbtn" id="tInvY">INVERT Y</button>
  <button class="tbtn" id="tSwap">SWAP X/Y</button>
</div>

<div class="mbtns">
  <button class="mbtn" id="lbtn"><div class="minner">LEFT</div></button>
  <button class="mbtn" id="rbtn"><div class="minner">RIGHT</div></button>
</div>

<div id="dbg">α:— β:—</div>

<script>
// ── Config (mutable via UI) ───────────────────────────────────────────────────
let sensitivity = 22;
let emaAlpha    = 0.55;  // 0..1 — higher = faster response, lower = smoother
const DEAD_ZONE = 0.18;  // degrees, filters sensor noise at rest

let invertX = false, invertY = false, swapXY = false;

// ── Runtime state ─────────────────────────────────────────────────────────────
let enabled = false;
let prevAlpha = null, prevBeta = null;
let emaX = 0, emaY = 0;
let ws;

// ── Geometry helpers ──────────────────────────────────────────────────────────
// Signed shortest arc between two angles (handles 0/360 wrap-around).
function angleDelta(curr, prev, range = 360) {{
  let d = curr - prev;
  const h = range / 2;
  if (d >  h) d -= range;
  if (d < -h) d += range;
  return d;
}}
// Dead zone with smooth edge (no jump at boundary).
function dz(v) {{
  if (Math.abs(v) < DEAD_ZONE) return 0;
  return v > 0 ? v - DEAD_ZONE : v + DEAD_ZONE;
}}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connect() {{
  ws = new WebSocket('{WS_SCHEME}://' + location.host + '/ws');
  ws.onopen  = () => setStatus('TRACKING — HEAD LEFT/RIGHT TO MOVE', 'on');
  ws.onclose = () => {{ setStatus('RECONNECTING…', 'err'); setTimeout(connect, 1200); }};
  ws.onerror = () => ws.close();
}}

// ── Enable motion (iOS 13+ requires user gesture + HTTPS) ─────────────────────
document.getElementById('enableBtn').addEventListener('click', async () => {{
  if (typeof DeviceOrientationEvent?.requestPermission === 'function') {{
    let p;
    try   {{ p = await DeviceOrientationEvent.requestPermission(); }}
    catch (e) {{ setStatus('ERR: ' + e.message, 'err'); return; }}
    if (p !== 'granted') {{ setStatus('PERMISSION DENIED', 'err'); return; }}
  }}
  enabled = true;
  prevAlpha = prevBeta = null;
  emaX = emaY = 0;
  const btn = document.getElementById('enableBtn');
  btn.textContent = '✓ ACTIVE';
  btn.classList.add('live');
  document.getElementById('dbg').classList.add('on');
  connect();
}});

// ── Device orientation → WebSocket ───────────────────────────────────────────
window.addEventListener('deviceorientation', e => {{
  if (!enabled || !ws || ws.readyState !== 1) return;

  const alpha = e.alpha ?? 0;  // compass/yaw  (0–360)  → horizontal
  const beta  = e.beta  ?? 0;  // pitch         (±180)  → vertical

  document.getElementById('dbg').textContent =
    'α:' + alpha.toFixed(1) + ' β:' + beta.toFixed(1);

  // First frame: anchor position, don't emit movement
  if (prevAlpha === null) {{ prevAlpha = alpha; prevBeta = beta; return; }}

  // Per-frame angular deltas (handles wrap-around at 0/360)
  let dH = dz(angleDelta(alpha, prevAlpha, 360));
  let dV = dz(angleDelta(beta,  prevBeta,  360));
  prevAlpha = alpha;
  prevBeta  = beta;

  // Axis transforms (adjust if movements feel wrong in your VR box)
  if (swapXY)  [dH, dV] = [dV, dH];
  if (invertX) dH = -dH;
  if (invertY) dV = -dV;

  // Low-pass filter: removes high-frequency jitter while preserving motion feel
  emaX = emaX * (1 - emaAlpha) + dH * emaAlpha;
  emaY = emaY * (1 - emaAlpha) + dV * emaAlpha;

  const dx = emaX * sensitivity;
  const dy = emaY * sensitivity;

  // Skip sub-pixel movements — prevents sensor spam at rest
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;

  // Plain "dx,dy" string — ~10x faster to parse than JSON on the server
  ws.send(dx.toFixed(1) + ',' + dy.toFixed(1));
}}, {{ passive: true }});

// ── Click buttons ─────────────────────────────────────────────────────────────
function sendClick(c) {{
  if (!ws || ws.readyState !== 1) return;
  ws.send('{{"c":"' + c + '"}}');
}}
['lbtn', 'rbtn'].forEach(id => {{
  const el = document.getElementById(id);
  const c  = id === 'lbtn' ? 'l' : 'r';
  // touchstart fires instantly, no 300ms iOS delay
  el.addEventListener('touchstart', e => {{ e.preventDefault(); sendClick(c); }}, {{passive: false}});
  el.addEventListener('mousedown',  () => sendClick(c));
}});

// ── Sliders ───────────────────────────────────────────────────────────────────
document.getElementById('sensSlider').addEventListener('input', e => {{
  sensitivity = +e.target.value;
  document.getElementById('sensVal').textContent = sensitivity;
}});
document.getElementById('emaSlider').addEventListener('input', e => {{
  emaAlpha = +e.target.value / 100;
  document.getElementById('emaVal').textContent = '.' + e.target.value;
  emaX = emaY = 0;  // flush stale EMA on change
}});

// ── Toggles ───────────────────────────────────────────────────────────────────
function bindToggle(id, cb) {{
  document.getElementById(id).addEventListener('click', function() {{
    this.classList.toggle('on'); cb(); emaX = emaY = 0;
  }});
}}
bindToggle('tInvX', () => invertX = !invertX);
bindToggle('tInvY', () => invertY = !invertY);
bindToggle('tSwap', () => swapXY  = !swapXY);

// ── Status helper ─────────────────────────────────────────────────────────────
function setStatus(msg, cls = '') {{
  const el = document.getElementById('status');
  el.className = cls;
  el.innerHTML = '<span class="dot"></span>' + msg;
}}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
async def handle_index(req):
    return web.Response(text=HTML, content_type='text/html')

async def handle_ws(req):
    ws = web.WebSocketResponse(
        max_msg_size=128,  # messages are tiny, cap for safety
        compress=False,    # no compression — raw speed only
    )
    await ws.prepare(req)

    # Disable Nagle's algorithm → TCP sends each packet immediately, not batched
    transport = ws._payload_writer.transport
    if hasattr(transport, 'get_extra_info'):
        sock = transport.get_extra_info('socket')
        if sock:
            import socket as _s
            try: sock.setsockopt(_s.IPPROTO_TCP, _s.TCP_NODELAY, 1)
            except Exception: pass

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            raw = msg.data
            try:
                if raw[0] == '{':
                    # Click command: {"c":"l"} or {"c":"r"}
                    d = json.loads(raw)
                    b = Button.right if d.get('c') == 'r' else Button.left
                    mouse.click(b)
                else:
                    # Move command: "dx,dy"  — no JSON overhead, just a split
                    i  = raw.index(',')
                    ix = int(float(raw[:i]))
                    iy = int(float(raw[i+1:]))
                    if ix or iy:
                        if abs(ix) > DANGER or abs(iy) > DANGER: pass
                        else: mouse.move(-ix, -iy)
                        print(f" Move: ({ix}, {iy})")
            except Exception:
                pass
        elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
            break

    return ws

# ─────────────────────────────────────────────────────────────────────────────
async def main():
    app = web.Application()
    app.router.add_get('/',   handle_index)
    app.router.add_get('/ws', handle_ws)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    print("\n" + "─" * 46)
    print("  🎯  VR Gyro Mouse  —  Maximum Performance")
    print("─" * 46)
    print(f"  📱  Open in iPhone Safari:")
    print(f"      \033[1;32m{SCHEME}://{IP}:{PORT}\033[0m")
    if SSL:
        print()
        print("  ⚠️   Safari will warn about the certificate.")
        print("       Tap  Advanced → Visit Website  to proceed.")
    print("─" * 46 + "\n")

    await asyncio.Event().wait()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")