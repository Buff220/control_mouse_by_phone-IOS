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
import time

PORT  = 6000
mouse = Controller()
DANGER=100
time.sleep(5)
mouse.press(Button.left)

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
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;background:#000;color:#fff;font-family:monospace}}
</style>
</head>
<body>

<button id="enableBtn">ENABLE</button>
<div id="dbg">α:— β:— γ:—</div>

<script>
let sensitivity = 22;
let emaAlpha    = 0.55;
const DEAD_ZONE = 0.18;

let enabled = false;
let prevAlpha = null, prevBeta = null, prevGamma = null;
let emaX = 0, emaY = 0, emaZ = 0;
let ws;

function angleDelta(curr, prev, range = 360) {{
  let d = curr - prev;
  const h = range / 2;
  if (d >  h) d -= range;
  if (d < -h) d += range;
  return d;
}}

function dz(v) {{
  if (Math.abs(v) < DEAD_ZONE) return 0;
  return v > 0 ? v - DEAD_ZONE : v + DEAD_ZONE;
}}

function connect() {{
  ws = new WebSocket('{WS_SCHEME}://' + location.host + '/ws');
}}

document.getElementById('enableBtn').addEventListener('click', async () => {{
  if (typeof DeviceOrientationEvent?.requestPermission === 'function') {{
    const p = await DeviceOrientationEvent.requestPermission();
    if (p !== 'granted') return;
  }}
  enabled = true;
  prevAlpha = prevBeta = prevGamma = null;
  emaX = emaY = emaZ = 0;
  connect();
}});

window.addEventListener('deviceorientation', e => {{
  if (!enabled || !ws || ws.readyState !== 1) return;

  const alpha = e.alpha ?? 0;
  const beta  = e.beta  ?? 0;
  const gamma = e.gamma ?? 0;

  document.getElementById('dbg').textContent =
    'α:' + alpha.toFixed(1) +
    ' β:' + beta.toFixed(1) +
    ' γ:' + gamma.toFixed(1);

  if (prevAlpha === null) {{
    prevAlpha = alpha;
    prevBeta  = beta;
    prevGamma = gamma;
    return;
  }}

  let dH = dz(angleDelta(alpha, prevAlpha, 360));
  let dV = dz(angleDelta(beta,  prevBeta,  360));
  let dZ = dz(angleDelta(gamma, prevGamma, 180));
  const MAX_DELTA = 8; // degrees per frame
dH = Math.max(-MAX_DELTA, Math.min(MAX_DELTA, dH));
dV = Math.max(-MAX_DELTA, Math.min(MAX_DELTA, dV));
dZ = Math.max(-MAX_DELTA, Math.min(MAX_DELTA, dZ));

  // Prevent Euler coupling explosion during strong Z rotation
  if (Math.abs(dZ) > Math.abs(dH) * 2 && Math.abs(dZ) > Math.abs(dV) * 2) {{
    dH = 0;
    dV = 0;
  }}


  prevAlpha = alpha;
  prevBeta  = beta;
  prevGamma = gamma;

  emaX = emaX * (1 - emaAlpha) + dH * emaAlpha;
  emaY = emaY * (1 - emaAlpha) + dV * emaAlpha;
  emaZ = emaZ * (1 - emaAlpha) + dZ * emaAlpha;
  
  // FINAL decoupling: prevent Z rotation from leaking into X/Y
if (Math.abs(emaZ) > Math.abs(emaX) * 1.2 &&
    Math.abs(emaZ) > Math.abs(emaY) * 1.2) {{
  emaX = 0;
  emaY = 0;
}}


  const dx = emaX * sensitivity;
  const dy = emaY * sensitivity;
  const dzv = emaZ * sensitivity;

  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(dzv) < 0.5) return;

  ws.send(dx.toFixed(1) + ',' + dy.toFixed(1) + ',' + dzv.toFixed(1));
}}, {{ passive: true }});
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
async def handle_index(req):
    return web.Response(text=HTML, content_type='text/html')

async def handle_ws(req):
    ws = web.WebSocketResponse(max_msg_size=128, compress=False)
    await ws.prepare(req)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            raw = msg.data
            try:
                if raw[0] == '{':
                    d = json.loads(raw)
                    b = Button.right if d.get('c') == 'r' else Button.left
                    mouse.click(b)
                else:
                    i1 = raw.index(',')
                    i2 = raw.index(',', i1 + 1)
                    ix = int(float(raw[:i1]))
                    iy = int(float(raw[i1+1:i2]))
                    iz = int(float(raw[i2+1:]))

                    if ix or iy or iz:
                        if abs(ix) > DANGER or abs(iy) > DANGER or abs(iz) > DANGER:
                            pass
                        else:
                            mouse.move(ix, -iz)
                        print(f" Move: ({ix}, {iy}, {iz})")
            except Exception:
                pass
    return ws

# ─────────────────────────────────────────────────────────────────────────────
async def main():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/ws', handle_ws)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    print(f"Open: {SCHEME}://{IP}:{PORT}")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
