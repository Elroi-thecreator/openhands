import asyncio
import glob
import hashlib
import hmac
import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import httpx
import websockets
import yaml

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


def is_request_authorized(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if verify_session_token(token):
        return True
    client_ip = request.client.host if request.client else ""
    if client_ip in ["127.0.0.1", "::1"] or client_ip.startswith("172.17.") or client_ip.startswith("172.18."):
        return True
    query_token = request.query_params.get("token")
    if verify_session_token(query_token):
        return True
    return False


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
        "active_tasks": len([t for t in _TASKS_STORE.values() if t.get("status") == "running"]),
        "active_subagents": len([s for s in _SUBAGENTS_STORE.values() if s.get("status") == "active"]),
        "active_schedules": len([j for j in _SCHEDULED_JOBS.values() if j.get("status") == "active"]),
        "recent_notifications": _NOTIFICATIONS_QUEUE[-5:],
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


@app.post("/gateway/api/auto-recover")
async def api_auto_recover(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    recovered_items = []
    try:
        subprocess.run(["sudo", "systemctl", "restart", "ollama"], check=True)
        recovered_items.append("Ollama local LLM daemon restarted")
    except Exception as e:
        recovered_items.append(f"Ollama restart: {e}")

    for tid, t in list(_TASKS_STORE.items()):
        if t.get("status") == "running" and (time.time() - t["created_at"] > 300):
            proc = _TASK_PROCESSES.get(tid)
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            t["status"] = "killed"
            t["finished_at"] = time.time()
            recovered_items.append(f"Terminated hanging task {tid}")

    logger.info(f"Antigravity Auto-Recover executed: {recovered_items}")
    return {"status": "ok", "actions": recovered_items}


@app.post("/gateway/api/model-fallback")
async def api_model_fallback(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    target_model = data.get("model", "local")
    settings_file = Path("/home/ubuntu/openhand/state/settings.json")
    if not settings_file.exists():
        return JSONResponse(status_code=404, content={"error": "settings.json not found"})
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        if target_model == "local":
            settings["llm_model"] = "ollama/qwen2.5-coder:1.5b"
            settings["llm_base_url"] = "http://host.docker.internal:11434"
            settings["llm_api_key"] = "ollama"
        else:
            settings["llm_model"] = "gemini/gemini-3-flash-preview"
            settings["llm_base_url"] = None
        settings_file.write_text(json.dumps(settings), encoding="utf-8")
        logger.info(f"Antigravity Model Fallback: active model is now {settings['llm_model']}")
        return {"status": "ok", "active_model": settings["llm_model"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/gateway/status", response_class=HTMLResponse)
@app.get("/status", response_class=HTMLResponse)
async def status_dashboard(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not verify_session_token(token):
        return RedirectResponse(url="/gateway/login?next=/gateway/status", status_code=302)
    return templates.TemplateResponse(request=request, name="status.html", context={})


# --- Antigravity Artifacts Engine ---
ARTIFACTS_DIR = Path("/home/ubuntu/openhand/workspace/artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_artifact_file(file_path: Path) -> dict:
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    stat = file_path.stat()
    meta = {
        "id": file_path.name,
        "filename": file_path.name,
        "title": file_path.stem.replace("_", " ").title(),
        "summary": "",
        "user_facing": True,
        "request_feedback": False,
        "approved": False,
        "updated_at": int(stat.st_mtime),
        "size": stat.st_size,
    }
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1])
                if isinstance(fm, dict):
                    meta.update({
                        "title": fm.get("title", meta["title"]),
                        "summary": fm.get("summary", ""),
                        "user_facing": fm.get("user_facing", True),
                        "request_feedback": fm.get("request_feedback", False),
                        "approved": fm.get("approved", False),
                    })
                    body = parts[2].strip()
            except Exception:
                pass

    if not meta["title"] or meta["title"] == file_path.stem.replace("_", " ").title():
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("# "):
                meta["title"] = line[2:].strip()
                break

    sidecar_app = file_path.parent / f".{file_path.name}.approved"
    if sidecar_app.exists():
        meta["approved"] = True

    return {
        "metadata": meta,
        "content": body,
        "raw": content,
    }


@app.get("/gateway/api/artifacts")
async def list_artifacts(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    items = []
    for p in sorted(ARTIFACTS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            parsed = parse_artifact_file(p)
            items.append(parsed["metadata"])
        except Exception as e:
            logger.warning(f"Error parsing artifact {p}: {e}")
    return {"artifacts": items, "count": len(items)}


@app.get("/gateway/api/artifacts/{filename}")
async def get_artifact(request: Request, filename: str):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    safe_name = Path(filename).name
    p = ARTIFACTS_DIR / safe_name
    if not p.exists() or not p.is_file():
        return JSONResponse(status_code=404, content={"error": "Artifact not found"})
    try:
        return parse_artifact_file(p)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/gateway/api/artifacts")
async def save_artifact(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    filename = Path(data.get("filename", f"artifact_{int(time.time())}.md")).name
    title = data.get("title", "")
    summary = data.get("summary", "")
    user_facing = data.get("user_facing", True)
    request_feedback = data.get("request_feedback", False)
    content = data.get("content", "")

    if not content.startswith("---"):
        frontmatter = f"""---
title: "{title or filename.replace('_', ' ').replace('.md', '').title()}"
summary: "{summary}"
user_facing: {str(user_facing).lower()}
request_feedback: {str(request_feedback).lower()}
approved: false
---

"""
        full_content = frontmatter + content
    else:
        full_content = content

    out_path = ARTIFACTS_DIR / filename
    out_path.write_text(full_content, encoding="utf-8")
    parsed = parse_artifact_file(out_path)
    logger.info(f"Saved Antigravity artifact: {filename} (title='{parsed['metadata']['title']}', feedback={request_feedback})")
    return {"status": "ok", "artifact": parsed["metadata"]}


@app.post("/gateway/api/artifacts/{filename}/approve")
async def approve_artifact(request: Request, filename: str):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    safe_name = Path(filename).name
    p = ARTIFACTS_DIR / safe_name
    if not p.exists():
        return JSONResponse(status_code=404, content={"error": "Artifact not found"})
    sidecar = p.parent / f".{safe_name}.approved"
    sidecar.write_text(json.dumps({"approved_at": time.time(), "status": "approved"}), encoding="utf-8")
    logger.info(f"Artifact {safe_name} approved by user.")
    return {"status": "ok", "filename": safe_name, "approved": True}


# --- Antigravity Structured Questions & Decision Cards Engine ---
_QUESTIONS_STORE: dict[str, dict] = {}
_QUESTIONS_EVENTS: dict[str, asyncio.Event] = {}


@app.post("/gateway/api/questions")
async def create_question(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    qid = str(uuid.uuid4())[:8]
    question = {
        "id": qid,
        "question": data.get("question", ""),
        "options": data.get("options", []),
        "is_multi_select": data.get("is_multi_select", False),
        "status": "pending",
        "answer": None,
        "created_at": time.time(),
    }
    _QUESTIONS_STORE[qid] = question
    _QUESTIONS_EVENTS[qid] = asyncio.Event()
    logger.info(f"Antigravity Question created [{qid}]: {question['question']} (options={question['options']})")
    return {"question_id": qid, "status": "pending", "question": question}


@app.get("/gateway/api/questions/pending")
async def get_pending_question(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    now = time.time()
    for qid in sorted(_QUESTIONS_STORE.keys(), key=lambda k: _QUESTIONS_STORE[k]["created_at"], reverse=True):
        q = _QUESTIONS_STORE[qid]
        if q["status"] == "pending" and (now - q["created_at"] < 300):
            return {"pending": True, "question": q}
    return {"pending": False, "question": None}


@app.post("/gateway/api/questions/{qid}/answer")
async def answer_question(request: Request, qid: str):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if qid not in _QUESTIONS_STORE:
        return JSONResponse(status_code=404, content={"error": "Question not found"})
    data = await request.json()
    answer = data.get("answer")
    _QUESTIONS_STORE[qid]["answer"] = answer
    _QUESTIONS_STORE[qid]["status"] = "answered"
    if qid in _QUESTIONS_EVENTS:
        _QUESTIONS_EVENTS[qid].set()
    logger.info(f"Antigravity Question answered [{qid}]: {answer}")
    return {"status": "ok", "question_id": qid, "answer": answer}


@app.get("/gateway/api/questions/{qid}/wait")
async def wait_question(request: Request, qid: str, timeout: int = 120):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if qid not in _QUESTIONS_STORE:
        return JSONResponse(status_code=404, content={"error": "Question not found"})
    q = _QUESTIONS_STORE[qid]
    if q["status"] == "answered":
        return {"status": "answered", "answer": q["answer"]}

    event = _QUESTIONS_EVENTS.get(qid)
    if not event:
        return {"status": "error", "message": "No event found for question"}

    try:
        await asyncio.wait_for(event.wait(), timeout=float(timeout))
        return {"status": "answered", "answer": _QUESTIONS_STORE[qid]["answer"]}
    except asyncio.TimeoutError:
        _QUESTIONS_STORE[qid]["status"] = "timeout"
        return {"status": "timeout", "answer": None}


# --- Antigravity Reactive Background Task & Schedule Engine ---
TASKS_LOG_DIR = Path("/home/ubuntu/openhand/state/tasks")
TASKS_LOG_DIR.mkdir(parents=True, exist_ok=True)

_TASKS_STORE: dict[str, dict] = {}
_TASK_PROCESSES: dict[str, asyncio.subprocess.Process] = {}
_TASK_LOGS: dict[str, list[str]] = {}

_SCHEDULED_JOBS: dict[str, dict] = {}
_SCHEDULE_TIMERS: dict[str, asyncio.Task] = {}
_NOTIFICATIONS_QUEUE: list[dict] = []


async def _run_monitored_subprocess(task_id: str, command: str, working_dir: str):
    log_file = TASKS_LOG_DIR / f"{task_id}.log"
    _TASK_LOGS[task_id] = []
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )
        _TASK_PROCESSES[task_id] = proc
        _TASKS_STORE[task_id]["pid"] = proc.pid

        with open(log_file, "a", encoding="utf-8") as f:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                f.write(decoded)
                f.flush()
                _TASK_LOGS[task_id].append(decoded)
                if len(_TASK_LOGS[task_id]) > 500:
                    _TASK_LOGS[task_id].pop(0)

        retcode = await proc.wait()
        _TASKS_STORE[task_id]["status"] = "completed" if retcode == 0 else "failed"
        _TASKS_STORE[task_id]["exit_code"] = retcode
        _TASKS_STORE[task_id]["finished_at"] = time.time()
        logger.info(f"Background Task {task_id} exited with code {retcode}")

        # Post notification
        _NOTIFICATIONS_QUEUE.append({
            "id": f"notif-{uuid.uuid4().hex[:6]}",
            "type": "task_completion",
            "task_id": task_id,
            "summary": _TASKS_STORE[task_id].get("tool_summary", command),
            "status": _TASKS_STORE[task_id]["status"],
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.error(f"Error running background task {task_id}: {e}")
        _TASKS_STORE[task_id]["status"] = "error"
        _TASKS_STORE[task_id]["error"] = str(e)
        _TASKS_STORE[task_id]["finished_at"] = time.time()
    finally:
        _TASK_PROCESSES.pop(task_id, None)


@app.post("/gateway/api/tasks/spawn")
async def spawn_background_task(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    command = data.get("command", "")
    summary = data.get("tool_summary", command[:40])
    working_dir = data.get("working_dir", "/home/ubuntu/openhand/workspace")

    if not command:
        return JSONResponse(status_code=400, content={"error": "Command is required"})

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    _TASKS_STORE[task_id] = {
        "id": task_id,
        "command": command,
        "tool_summary": summary,
        "working_dir": working_dir,
        "status": "running",
        "pid": None,
        "exit_code": None,
        "created_at": time.time(),
        "finished_at": None,
    }

    asyncio.create_task(_run_monitored_subprocess(task_id, command, working_dir))
    logger.info(f"Spawned Background Task: {task_id} -> {summary}")
    return {"task_id": task_id, "status": "running", "task": _TASKS_STORE[task_id]}


@app.get("/gateway/api/tasks")
async def list_background_tasks(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    tasks_list = sorted(_TASKS_STORE.values(), key=lambda t: t["created_at"], reverse=True)
    return {"tasks": tasks_list, "count": len(tasks_list)}


@app.get("/gateway/api/tasks/{task_id}")
async def get_background_task(request: Request, task_id: str, tail: int = 50):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if task_id not in _TASKS_STORE:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    logs = _TASK_LOGS.get(task_id, [])[-tail:]
    if not logs:
        log_file = TASKS_LOG_DIR / f"{task_id}.log"
        if log_file.exists():
            try:
                lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
                logs = lines[-tail:]
            except Exception:
                pass

    return {
        "task": _TASKS_STORE[task_id],
        "logs": "".join(logs),
        "recent_lines": [l.strip() for l in logs[-15:]],
    }


@app.post("/gateway/api/tasks/{task_id}/input")
async def send_task_input(request: Request, task_id: str):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if task_id not in _TASK_PROCESSES:
        return JSONResponse(status_code=404, content={"error": "Active task process not found"})

    data = await request.json()
    input_text = data.get("input", "")
    proc = _TASK_PROCESSES[task_id]

    try:
        if proc.stdin and not proc.stdin.is_closing():
            proc.stdin.write(input_text.encode("utf-8"))
            await proc.stdin.drain()
            return {"status": "ok", "delivered_bytes": len(input_text)}
        return JSONResponse(status_code=400, content={"error": "Process stdin not available"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/gateway/api/tasks/{task_id}/kill")
async def kill_background_task(request: Request, task_id: str):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if task_id not in _TASKS_STORE:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    proc = _TASK_PROCESSES.get(task_id)
    if proc:
        try:
            proc.terminate()
            await asyncio.sleep(0.5)
            if proc.returncode is None:
                proc.kill()
        except Exception:
            pass

    _TASKS_STORE[task_id]["status"] = "killed"
    _TASKS_STORE[task_id]["finished_at"] = time.time()
    return {"status": "ok", "task_id": task_id, "state": "killed"}


# --- Antigravity Reactive Scheduler ---
async def _schedule_timer_worker(job_id: str, duration: int, prompt: str):
    try:
        await asyncio.sleep(duration)
        if job_id in _SCHEDULED_JOBS:
            _SCHEDULED_JOBS[job_id]["status"] = "triggered"
            _SCHEDULED_JOBS[job_id]["triggered_at"] = time.time()
            logger.info(f"Timer {job_id} fired: '{prompt}'")
            _NOTIFICATIONS_QUEUE.append({
                "id": f"notif-{uuid.uuid4().hex[:6]}",
                "type": "timer_trigger",
                "job_id": job_id,
                "prompt": prompt,
                "timestamp": time.time(),
            })
    except asyncio.CancelledError:
        if job_id in _SCHEDULED_JOBS:
            _SCHEDULED_JOBS[job_id]["status"] = "cancelled"
    finally:
        _SCHEDULE_TIMERS.pop(job_id, None)


@app.post("/gateway/api/schedule")
async def register_schedule(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    prompt = data.get("prompt", "")
    duration = data.get("duration_seconds")
    cron_expr = data.get("cron_expression")
    timer_condition = data.get("timer_condition", "never")

    if not prompt:
        return JSONResponse(status_code=400, content={"error": "Prompt is required"})

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    _SCHEDULED_JOBS[job_id] = {
        "id": job_id,
        "prompt": prompt,
        "duration_seconds": duration,
        "cron_expression": cron_expr,
        "timer_condition": timer_condition,
        "status": "active",
        "created_at": time.time(),
        "triggered_at": None,
    }

    if duration and duration > 0:
        task = asyncio.create_task(_schedule_timer_worker(job_id, duration, prompt))
        _SCHEDULE_TIMERS[job_id] = task

    logger.info(f"Registered Antigravity Schedule [{job_id}]: {prompt} (duration={duration}s)")
    return {"schedule_id": job_id, "status": "active", "job": _SCHEDULED_JOBS[job_id]}


@app.get("/gateway/api/schedule")
async def list_schedules(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    jobs = sorted(_SCHEDULED_JOBS.values(), key=lambda j: j["created_at"], reverse=True)
    return {"schedules": jobs, "notifications": _NOTIFICATIONS_QUEUE[-20:]}


@app.delete("/gateway/api/schedule/{job_id}")
async def cancel_schedule(request: Request, job_id: str):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if job_id not in _SCHEDULED_JOBS:
        return JSONResponse(status_code=404, content={"error": "Schedule not found"})

    timer = _SCHEDULE_TIMERS.get(job_id)
    if timer:
        timer.cancel()

    _SCHEDULED_JOBS[job_id]["status"] = "cancelled"
    return {"status": "ok", "job_id": job_id, "state": "cancelled"}


# --- Antigravity Subagents & Inter-Agent Mailbox Engine ---
_SUBAGENTS_STORE: dict[str, dict] = {}
_AGENT_MESSAGES: list[dict] = []


@app.post("/gateway/api/subagents")
async def invoke_subagent(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    role = data.get("role", "General Subagent")
    type_name = data.get("type_name", "subagent")
    prompt = data.get("prompt", "")
    workspace_mode = data.get("workspace", "inherit")
    model = data.get("model", "inherit")

    cid = f"subagent-{uuid.uuid4().hex[:8]}"
    sub_dir = Path("/home/ubuntu/openhand/workspace")
    if workspace_mode in ["branch", "share"]:
        sub_dir = Path(f"/home/ubuntu/openhand/workspace/.subagents/{cid}")
        sub_dir.mkdir(parents=True, exist_ok=True)

    subagent = {
        "conversation_id": cid,
        "type_name": type_name,
        "role": role,
        "prompt": prompt,
        "workspace_mode": workspace_mode,
        "workspace_dir": str(sub_dir),
        "model": model,
        "status": "active",
        "created_at": time.time(),
        "finished_at": None,
    }
    _SUBAGENTS_STORE[cid] = subagent
    logger.info(f"Invoked Antigravity Subagent: {cid} (Role: '{role}', Mode: {workspace_mode})")
    return {"conversation_id": cid, "status": "active", "subagent": subagent}


@app.get("/gateway/api/subagents")
async def list_subagents(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    subs = sorted(_SUBAGENTS_STORE.values(), key=lambda s: s["created_at"], reverse=True)
    return {"subagents": subs, "count": len(subs)}


@app.post("/gateway/api/messages")
async def send_agent_message(request: Request):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    data = await request.json()
    recipient = data.get("recipient", "")
    sender = data.get("sender", "coordinator")
    msg_content = data.get("message", "")

    if not recipient or not msg_content:
        return JSONResponse(status_code=400, content={"error": "Recipient and message are required"})

    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    msg_obj = {
        "id": msg_id,
        "recipient": recipient,
        "sender": sender,
        "message": msg_content,
        "timestamp": time.time(),
        "read": False,
    }
    _AGENT_MESSAGES.append(msg_obj)
    logger.info(f"Agent Message from {sender} -> {recipient}: {msg_content[:40]}...")
    return {"status": "delivered", "message_id": msg_id, "message": msg_obj}


@app.get("/gateway/api/messages")
async def get_agent_messages(request: Request, recipient: Optional[str] = None, unread_only: bool = False):
    if not is_request_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    filtered = _AGENT_MESSAGES
    if recipient:
        filtered = [m for m in filtered if m["recipient"] == recipient]
    if unread_only:
        filtered = [m for m in filtered if not m["read"]]
    return {"messages": filtered, "count": len(filtered)}


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
          let extra = '';
          if (d.active_tasks > 0) extra += ' • ' + d.active_tasks + ' Task' + (d.active_tasks > 1 ? 's' : '');
          if (d.active_subagents > 0) extra += ' • ' + d.active_subagents + ' Sub';
          cpu.textContent = 'RAM: ' + (d.mem_avail_mb / 1024).toFixed(1) + 'G' + extra;
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
