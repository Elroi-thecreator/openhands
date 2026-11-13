import asyncio
import glob
import hashlib
import hmac
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import httpx
import websockets

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("openhands-gateway")

# Gateway Configuration
GATEWAY_USERNAME = os.getenv("GATEWAY_USERNAME", "admin")
GATEWAY_PASSWORD = os.getenv("GATEWAY_PASSWORD", "openhands123!")
SECRET_KEY = os.getenv("SECRET_KEY", "openhands-super-secret-key-change-me")
COOKIE_NAME = "openhands_auth"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 7))) # 7 days
BACKEND_HTTP_URL = os.getenv("OPENHANDS_BACKEND_URL", "http://127.0.0.1:3000")
BACKEND_WS_URL = os.getenv("OPENHANDS_WS_URL", "ws://127.0.0.1:3000")

# Setup templates
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="OpenHands Auth Gateway", docs_url=None, redoc_url=None, openapi_url=None)

# HTTP Client for proxying
http_client = httpx.AsyncClient(base_url=BACKEND_HTTP_URL, timeout=None, follow_redirects=False)


@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()


# --- Authentication Helpers ---
def create_session_token(username: str) -> str:
    timestamp = int(time.time())
    payload = f"{username}:{timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: Optional[str]) -> bool:
    if not token:
        return False
    parts = token.split(":")
    if len(parts) != 3:
        return False
    username, timestamp_str, signature = parts
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False
    if time.time() - timestamp > SESSION_MAX_AGE:
        return False
    expected_payload = f"{username}:{timestamp_str}"
    expected_sig = hmac.new(SECRET_KEY.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_sig) and (username == GATEWAY_USERNAME)


# Hop-by-hop headers that should not be forwarded
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


# --- Auth Routes ---
@app.api_route("/gateway/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    token = request.cookies.get(COOKIE_NAME)
    if verify_session_token(token):
        return RedirectResponse(url=next or "/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None, "next_url": next})


@app.post("/gateway/login")
@app.post("/login")
async def login_action(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    next_url = form.get("next", "/") or "/"

    if username == GATEWAY_USERNAME and password == GATEWAY_PASSWORD:
        token = create_session_token(username)
        response = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )
        logger.info(f"Successful login for user '{username}' from {request.client.host if request.client else 'unknown'}")
        return response

    logger.warning(f"Failed login attempt for user '{username}' from {request.client.host if request.client else 'unknown'}")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password.", "next_url": next_url},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get("/gateway/logout")
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/gateway/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response


@app.api_route("/gateway/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "service": "openhands-auth-gateway"}


# --- Antigravity Live Status & Monitoring ---
_STATUS_CACHE = {
    "last_check": 0.0,
    "cached_data": None,
    "sandboxes": 0,
    "sandboxes_check": 0.0,
    "ollama_cpu": 0.0,
    "ollama_active": False,
    "ollama_check": 0.0,
}


def get_live_status_data():
    now = time.time()
    if _STATUS_CACHE["cached_data"] and (now - _STATUS_CACHE["last_check"] < 1.5):
        return _STATUS_CACHE["cached_data"]

    mem_avail = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1]) // 1024  # MB
                    break
    except Exception:
        pass

    load1, _, _ = os.getloadavg()

    if now - _STATUS_CACHE["ollama_check"] >= 2.0:
        ollama_active = False
        ollama_cpu = 0.0
        try:
            ps_out = subprocess.check_output(["ps", "-C", "llama-server", "-o", "%cpu="], text=True).strip()
            if ps_out:
                ollama_cpu = float(ps_out.split()[0])
                ollama_active = ollama_cpu > 10.0
        except Exception:
            pass
        _STATUS_CACHE["ollama_active"] = ollama_active
        _STATUS_CACHE["ollama_cpu"] = ollama_cpu
        _STATUS_CACHE["ollama_check"] = now
    else:
        ollama_active = _STATUS_CACHE["ollama_active"]
        ollama_cpu = _STATUS_CACHE["ollama_cpu"]

    if now - _STATUS_CACHE["sandboxes_check"] >= 5.0:
        active_sandboxes = 0
        try:
            sb_out = subprocess.check_output(["sudo", "docker", "ps", "-q", "--filter", "name=openhands-runtime"], text=True).strip()
            active_sandboxes = len(sb_out.splitlines()) if sb_out else 0
        except Exception:
            pass
        _STATUS_CACHE["sandboxes"] = active_sandboxes
        _STATUS_CACHE["sandboxes_check"] = now
    else:
        active_sandboxes = _STATUS_CACHE["sandboxes"]

    sessions = sorted(glob.glob("/home/ubuntu/openhand/state/sessions/*"), key=os.path.getmtime, reverse=True)
    last_action = "idle"
    last_msg = ""
    last_source = ""
    session_title = ""
    recent_events = []

    if sessions:
        latest = sessions[0]
        meta_file = os.path.join(latest, "metadata.json")
        if os.path.exists(meta_file):
            try:
                meta = json.load(open(meta_file))
                session_title = meta.get("title", "")
            except Exception:
                pass

        event_files = sorted(
            glob.glob(os.path.join(latest, "events", "*.json")),
            key=lambda p: int(os.path.splitext(os.path.basename(p))[0]) if os.path.splitext(os.path.basename(p))[0].isdigit() else 0
        )
        if event_files:
            try:
                ev = json.load(open(event_files[-1]))
                last_action = ev.get("action", "idle")
                last_source = ev.get("source", "")
                last_msg = str(ev.get("message") or ev.get("args", {}).get("content") or "")[:120]
            except Exception:
                pass

            for ef in event_files[-5:]:
                try:
                    e = json.load(open(ef))
                    content = str(e.get("message") or e.get("args", {}).get("content") or e.get("args", {}).get("thought") or "")[:150]
                    t = e.get("timestamp", "")
                    if "T" in t:
                        t = t.split("T")[1][:8]
                    recent_events.append({
                        "id": e.get("id"),
                        "source": e.get("source", ""),
                        "action": e.get("action", ""),
                        "content": content,
                        "time": t
                    })
                except Exception:
                    pass

    agent_state = "thinking" if ollama_active else ("running_action" if last_source == "agent" else "idle")

    data = {
        "agent_state": agent_state,
        "last_action": last_action,
        "last_message": last_msg,
        "last_source": last_source,
        "session_title": session_title,
        "mem_avail_mb": mem_avail,
        "cpu_load1": round(load1, 2),
        "ollama_active": ollama_active,
        "ollama_cpu": ollama_cpu,
        "active_sandboxes": active_sandboxes,
        "recent_events": recent_events[::-1]
    }
    _STATUS_CACHE["cached_data"] = data
    _STATUS_CACHE["last_check"] = now
    return data


@app.get("/gateway/api/live")
async def api_live(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not verify_session_token(token):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return get_live_status_data()


@app.post("/gateway/api/restart-ollama")
async def api_restart_ollama(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not verify_session_token(token):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        subprocess.run(["sudo", "systemctl", "restart", "ollama"], check=True)
        return {"status": "ok", "message": "Ollama restarted"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/gateway/status", response_class=HTMLResponse)
@app.get("/status", response_class=HTMLResponse)
async def status_dashboard(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not verify_session_token(token):
        return RedirectResponse(url="/gateway/login?next=/gateway/status", status_code=302)
    return templates.TemplateResponse(request=request, name="status.html", context={})


# --- WebSocket Proxy ---
@app.websocket("/{full_path:path}")
async def websocket_proxy(websocket: WebSocket, full_path: str):
    # Verify auth from cookie or query token
    token = websocket.cookies.get(COOKIE_NAME)
    if not verify_session_token(token):
        query_token = websocket.query_params.get("token")
        if not verify_session_token(query_token):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
            return

    await websocket.accept()

    query_str = str(websocket.url.query)
    target_url = f"{BACKEND_WS_URL}/{full_path}"
    if query_str:
        target_url = f"{target_url}?{query_str}"

    headers = {}
    for h, v in websocket.headers.items():
        if h.lower() not in HOP_BY_HOP_HEADERS and not h.lower().startswith("sec-websocket-"):
            headers[h] = v

    try:
        async with websockets.connect(
            target_url,
            additional_headers=headers,
            subprotocols=websocket.headers.get("sec-websocket-protocol", "").split(",") if websocket.headers.get("sec-websocket-protocol") else None,
            ping_interval=30,
            ping_timeout=30,
            max_size=None,
        ) as backend_ws:
            async def forward_client_to_backend():
                try:
                    while True:
                        msg = await websocket.receive()
                        if "text" in msg:
                            await backend_ws.send(msg["text"])
                        elif "bytes" in msg:
                            await backend_ws.send(msg["bytes"])
                        elif msg.get("type") == "websocket.disconnect":
                            break
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug(f"WS client->backend closed: {e}")

            async def forward_backend_to_client():
                try:
                    async for msg in backend_ws:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        elif isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                except Exception as e:
                    logger.debug(f"WS backend->client closed: {e}")

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(forward_client_to_backend()),
                    asyncio.create_task(forward_backend_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error(f"WebSocket proxy connection to backend failed: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Backend unavailable")
        except:
            pass


# --- Catch-All HTTP Reverse Proxy ---
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def http_proxy(request: Request, full_path: str):
    token = request.cookies.get(COOKIE_NAME)
    is_authenticated = verify_session_token(token)

    if not is_authenticated:
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header or request.method in ["GET", "HEAD"]:
            next_url = str(request.url.path)
            if request.url.query:
                next_url += f"?{request.url.query}"
            return RedirectResponse(url=f"/gateway/login?next={next_url}", status_code=status.HTTP_302_FOUND)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Unauthorized", "message": "Please log in at /gateway/login"}
        )

    # Prepare forwarded headers
    forward_headers = {}
    for key, value in request.headers.items():
        if key.lower() not in HOP_BY_HOP_HEADERS:
            forward_headers[key] = value

    client_ip = request.client.host if request.client else "127.0.0.1"
    forward_headers["x-forwarded-for"] = client_ip
    forward_headers["x-forwarded-proto"] = request.url.scheme
    forward_headers["x-forwarded-host"] = request.headers.get("host", "127.0.0.1")

    target_path = f"/{full_path}"
    if request.url.query:
        target_path += f"?{request.url.query}"

    try:
        backend_req = http_client.build_request(
            method=request.method,
            url=target_path,
            headers=forward_headers,
            content=request.stream(),
        )
        backend_resp = await http_client.send(backend_req, stream=True)

        resp_headers = {}
        for k, v in backend_resp.headers.items():
            if k.lower() not in HOP_BY_HOP_HEADERS:
                resp_headers[k] = v

        # Inject Antigravity Live Status HUD and Theme on all HTML pages
        if "text/html" in resp_headers.get("content-type", ""):
            body = await backend_resp.aread()
            html_text = body.decode("utf-8", errors="ignore")
            hud_snippet = """
<!-- Google Antigravity Theme & Live HUD Injection -->
<link rel="stylesheet" href="/assets/antigravity.css"/>
<script src="/assets/antigravity-shell.js" defer></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
  
  /* Floating Antigravity Status HUD Pill */
  #ag-hud-container {
    position: fixed;
    bottom: 14px;
    right: 18px;
    z-index: 999999;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  #ag-hud-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(13, 18, 32, 0.94);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 20px;
    padding: 6px 14px;
    color: #f8fafc;
    text-decoration: none;
    font-size: 12px;
    font-weight: 500;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 14px rgba(139, 92, 246, 0.15);
    transition: all 0.2s ease;
  }
  #ag-hud-pill:hover {
    border-color: #8b5cf6;
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6), 0 0 20px rgba(139, 92, 246, 0.25);
  }

  /* Suppress the blocking runtime startup timer and spinner from chat input */
  [data-testid="agent-loading-spinner"],
  span[title*="Starting runtime"],
  span[title*="Laufzeitumgebung"],
  span[title*="Starting"] {
    display: none !important;
  }
</style>

<div id="ag-hud-container">
  <a href="/gateway/status" target="_blank" id="ag-hud-pill" title="Click to open Antigravity Live Status">
    <span id="ag-hud-dot" style="width:8px;height:8px;border-radius:50%;background:#10b981;display:inline-block;"></span>
    <span id="ag-hud-brand" style="font-weight:700;background:linear-gradient(135deg, #a5b4fc 0%, #c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Antigravity</span>
    <span style="opacity:0.3;color:#64748b;">|</span>
    <span id="ag-hud-text" style="font-weight:500;color:#cbd5e1;">Idle</span>
    <span style="opacity:0.3;color:#64748b;">|</span>
    <span id="ag-hud-cpu" style="color:#94a3b8;">RAM: 7.8G</span>
    <span style="opacity:0.6;font-size:10px;color:#818cf8;">↗</span>
  </a>
</div>

<script>
  (function() {
    let debounceTimer = null;
    let observer = null;

    function transformBranding() {
      if (document.title.includes('OpenHands')) {
        document.title = document.title.replace('OpenHands', 'Antigravity');
      }
      if (observer) observer.disconnect();
      try {
        const candidates = document.querySelectorAll('span, p, h1, div, a');
        for (let i = 0; i < candidates.length; i++) {
          const el = candidates[i];
          if (el.children.length === 0) {
            const txt = el.textContent.trim();
            if (txt === 'All Hands AI' || txt === 'OpenHands') {
              el.innerHTML = '<span style=\"background:linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #38bdf8 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:700;\">Antigravity</span>';
            }
          }
        }
      } catch (e) {
      } finally {
        if (observer) {
          observer.observe(document.body, { childList: true, subtree: true });
        }
      }
    }

    function scheduleTransform() {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(transformBranding, 400);
    }

    observer = new MutationObserver(scheduleTransform);
    observer.observe(document.body, { childList: true, subtree: true });
    scheduleTransform();

    async function updateAgHud() {
      try {
        const res = await fetch('/gateway/api/live');
        if (!res.ok) return;
        const d = await res.json();
        const dot = document.getElementById('ag-hud-dot');
        const txt = document.getElementById('ag-hud-text');
        const cpu = document.getElementById('ag-hud-cpu');
        if (dot && txt && cpu) {
          if (d.agent_state === 'thinking') {
            dot.style.background = '#f59e0b';
            txt.textContent = 'Thinking (' + d.ollama_cpu.toFixed(0) + '% CPU)';
          } else if (d.agent_state === 'running_action') {
            dot.style.background = '#10b981';
            txt.textContent = d.last_action;
          } else {
            dot.style.background = '#8b5cf6';
            txt.textContent = d.last_action || 'Idle';
          }
          cpu.textContent = 'RAM: ' + (d.mem_avail_mb / 1024).toFixed(1) + 'G';
        }
      } catch (e) {}
    }

    setInterval(updateAgHud, 3000);
    setTimeout(updateAgHud, 500);
  })();
</script>
</body>
"""
            html_text = html_text.replace("</body>", hud_snippet)
            filtered_headers = {k: v for k, v in resp_headers.items() if k.lower() != "content-length"}
            return HTMLResponse(content=html_text, status_code=backend_resp.status_code, headers=filtered_headers)

        return StreamingResponse(
            backend_resp.aiter_bytes(),
            status_code=backend_resp.status_code,
            headers=resp_headers,
            background=backend_resp.aclose,
        )

    except httpx.ConnectError:
        return HTMLResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="""
            <!DOCTYPE html>
            <html>
            <head><meta charset="utf-8"><title>OpenHands Starting</title>
            <meta http-equiv="refresh" content="5">
            <style>
              body { background: #0d1117; color: #c9d1d9; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
              .box { text-align: center; background: #161b22; padding: 40px; border-radius: 12px; border: 1px solid #30363d; max-width: 480px; }
              h2 { color: #58a6ff; margin-bottom: 12px; }
              p { color: #8b949e; line-height: 1.5; }
              .spinner { margin: 20px auto; width: 36px; height: 36px; border: 3px solid #30363d; border-top-color: #58a6ff; border-radius: 50%; animation: spin 1s infinite linear; }
              @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
            </head>
            <body>
              <div class="box">
                <div class="spinner"></div>
                <h2>OpenHands is Starting Up</h2>
                <p>The OpenHands backend container is initializing. This page will refresh automatically every 5 seconds...</p>
              </div>
            </body>
            </html>
            """,
        )
    except Exception as e:
        logger.error(f"Proxy request error: {e}")
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"error": "Bad Gateway", "details": str(e)})
