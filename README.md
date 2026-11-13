# OpenHands Autonomous Agent Platform

A production-grade, hardened, and high-performance deployment of [OpenHands](https://github.com/All-Hands-AI/OpenHands) optimized for cloud infrastructure (Oracle Cloud Infrastructure Always-Free 2-vCPU / 12GB RAM instances) with reverse proxy authentication, real-time live telemetry HUD, persistent tool patches, and zero-cold-start standby sandboxes.

---

## Architecture Overview

```
                      Internet (HTTPS:8443)
                                │
                                ▼
                       Nginx SSL Proxy
             (Let's Encrypt + Gzip + Asset Caching)
                                │
                                ▼
                   FastAPI Web Gateway (8080)
           (HMAC-SHA256 Session Auth + HUD Telemetry)
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
       REST HTTP Reverse Proxy          WebSocket Tunnel
                │                               │
                └───────────────┬───────────────┘
                                ▼
                   OpenHands Backend (3000)
                 (Bound strictly to 127.0.0.1)
                                │
                                ▼ Docker Socket
                 Docker Runtime Sandbox Container
             (ghcr.io/all-hands-ai/runtime:latest-nikolaik)
```

---

## Core Capabilities & Performance Optimizations

1. **Instant Task Execution (Zero-Cold-Start)**:
   - Configured with `SANDBOX_KEEP_RUNTIME_ALIVE=true` and a managed 1-container warm standby pool.
   - Eliminates the 45-second container boot delay on new tasks (`0.001s` attachment).
2. **LLM Context & Prompt Compression**:
   - High-throughput `gemini/gemini-3-flash-preview` integration (1M context, 15 RPM free tier).
   - Dynamic conversation event condensation (`condenser_max_size: 35`) preventing context window bloat and maintaining sub-2s turn latency.
3. **Tool Parameter Decoupling & Hotfix Patches**:
   - Patched CodeAct tools (`execute_bash`, `str_replace_editor`, `ipython`, `browser`, `llm_based_edit`) and `fn_call_converter.py` mounted persistently from `patches/` to decouple auxiliary `security_risk` parameters and prevent XML parser validation errors.
4. **Secure Reverse Proxy & Authentication Gateway**:
   - FastAPI gateway enforcing cryptographically signed `openhands_auth` session cookies.
   - Reverse-proxies WebSockets with `max_size=None` for arbitrary diff and file transfer streaming.
   - Built-in Antigravity real-time telemetry HUD overlay on all workspace pages.
5. **Nginx Caching & Gzip Compression**:
   - 30-day immutable caching for static React/Vite assets (`/assets/`, `/static/`).
   - Gzip compression on dynamic API JSON responses, reducing payload sizes by ~80%.
6. **SRE Capacity & Budget Monitoring**:
   - Built-in `vm-budget-check` tool enforcing disk (<75%), memory (2+ GB headroom), and single-standby container lifecycle.

---

## Directory Structure

```
.
├── docker-compose.yml           # OpenHands container orchestration & volume mounts
├── .env.example                 # Example environment variables for OpenHands
├── gateway/                     # FastAPI reverse proxy, authentication & HUD dashboard
│   ├── main.py                  # Proxy routing, WebSocket tunnel & HUD injection
│   ├── templates/               # Login & status HTML templates
│   └── .env.example             # Gateway auth credentials template
├── knowledge/                   # Standardized architectural & development knowledge base
│   ├── architecture/            # ARCH standards (deployment, gateway, networking)
│   ├── development/             # DEV standards (budget, ops, proxy, tools)
│   ├── product/                 # PROD standards (LLM, auth, antigravity)
│   ├── decisions/               # Architecture Decision Records (ADRs)
│   └── index.yaml               # Master knowledge graph index
├── patches/                     # Persistent Python tool patches mounted into container
│   ├── bash.py                  # Decoupled security_risk in execute_bash
│   ├── str_replace_editor.py    # Decoupled security_risk in editor
│   ├── ipython.py               # Decoupled security_risk in ipython
│   ├── browser.py               # Decoupled security_risk in browser
│   ├── llm_based_edit.py        # Decoupled security_risk in llm edit
│   └── fn_call_converter.py     # Fault-tolerant XML tool call parser
├── scripts/                     # Operational, testing & benchmarking utilities
│   ├── budget_check.py          # VM capacity & container budget enforcement tool
│   ├── e2e_live_test.py         # Full automated end-to-end live testing suite
│   ├── test_webapp_creation.py  # End-to-end webapp creation benchmark
│   └── watch_agent.py           # Real-time console agent event watcher
└── workspace/                   # Isolated agent workspace & generated projects
    ├── AGENTS.md                # Agent execution protocol & multi-file batching rules
    └── webapp/                  # Tested responsive Task Tracker web application
```

---

## Quickstart

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Google AI Studio API key

cp gateway/.env.example gateway/.env
# Edit gateway/.env with your gateway password and session secret
```

### 2. Start Services
```bash
# Start OpenHands container
docker compose up -d

# Start Gateway service
sudo systemctl restart openhands-gateway.service

# Verify health & capacity budget
vm-budget-check
```

### 3. Run End-to-End Live Verification
```bash
./gateway/.venv/bin/python scripts/e2e_live_test.py
./gateway/.venv/bin/python scripts/test_webapp_creation.py
```
