#!/usr/bin/env python3
"""
Simple Webapp Creation Performance Benchmark for OpenHands
Measures exact end-to-end timing:
- Authentication & Conversation initialization
- Docker sandbox container spin-up & MCP initialization
- Time to First Thought/Action (TTFT)
- Tool execution latency (file creation, bash commands)
- Total turn completion time
- Workspace file verification on host
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
import websockets

BASE_HTTP = "http://127.0.0.1:8080"
BASE_WS = "ws://127.0.0.1:8080"
WORKSPACE_DIR = Path("/home/ubuntu/openhand/workspace/webapp")

WEBAPP_PROMPT = """Create a complete responsive modern Task Tracker web application in /workspace/webapp.
It must contain:
1. index.html - Semantic HTML5 layout with an app title, an input field to add new tasks, priority selector (Low, Medium, High), filter buttons (All, Active, Completed), and a task list container.
2. styles.css - Clean CSS styling with modern typography, dark/light theme accents, smooth button hover animations, card shadows, and mobile responsiveness.
3. app.js - ES6 JavaScript for adding tasks, toggling completion, filtering tasks, and saving/loading tasks from localStorage.
Create all three files and verify that /workspace/webapp contains index.html, styles.css, and app.js."""


async def run_benchmark():
    print("=" * 72)
    print("⚡ OPENHANDS WEBAPP CREATION PERFORMANCE BENCHMARK")
    print("=" * 72)

    # Clean target directory before test
    if WORKSPACE_DIR.exists():
        for item in WORKSPACE_DIR.glob("*"):
            if item.is_file():
                item.unlink()
    else:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    timing = {}
    benchmark_start = time.time()

    # Step 1: Gateway Authentication
    print("\n[Step 1] Gateway Authentication...")
    gw_env = Path("/home/ubuntu/openhand/gateway/.env")
    password = "QZSlXi1VKkbyTUUY"
    if gw_env.exists():
        for line in gw_env.read_text().splitlines():
            if line.startswith("GATEWAY_PASSWORD="):
                password = line.split("=", 1)[1].strip()

    t0 = time.time()
    async with httpx.AsyncClient(base_url=BASE_HTTP, timeout=30.0) as client:
        resp = await client.post(
            "/gateway/login",
            data={"username": "admin", "password": password, "next": "/"},
        )
        assert resp.status_code == 302, f"Login failed: {resp.status_code}"
        auth_cookie = client.cookies.get("openhands_auth")
        assert auth_cookie, "Missing auth cookie"
        timing["auth_ms"] = (time.time() - t0) * 1000
        print(f"  ✓ Authenticated in {timing['auth_ms']:.1f}ms")

        # Step 2: Config Check
        print("\n[Step 2] Backend Configuration Verification...")
        t0 = time.time()
        cfg_resp = await client.get("/api/options/config", cookies={"openhands_auth": auth_cookie})
        assert cfg_resp.status_code == 200
        cfg = cfg_resp.json()
        model_name = cfg.get("llm_model", "unknown")
        timing["config_ms"] = (time.time() - t0) * 1000
        print(f"  ✓ Config checked in {timing['config_ms']:.1f}ms (Active Model: {model_name})")

        # Step 3: Conversation Creation with Prompt
        print("\n[Step 3] Dispatching Webapp Creation Task...")
        t0 = time.time()
        conv_resp = await client.post(
            "/api/conversations",
            json={"initial_user_msg": WEBAPP_PROMPT},
            cookies={"openhands_auth": auth_cookie},
        )
        assert conv_resp.status_code in [200, 201], f"Failed to create conversation: {conv_resp.status_code}"
        conversation_id = conv_resp.json()["conversation_id"]
        timing["conv_create_ms"] = (time.time() - t0) * 1000
        print(f"  ✓ Conversation initialized in {timing['conv_create_ms']:.1f}ms (ID: {conversation_id})")

    # Step 4: Real-time WebSocket Monitoring
    print("\n[Step 4] Monitoring Agent Execution Stream via WebSocket...")
    ws_url = (
        f"{BASE_WS}/socket.io/?EIO=4&transport=websocket"
        f"&conversation_id={conversation_id}&providers_set=github"
    )

    ws_start = time.time()
    first_thought_time = None
    runtime_ready_time = None
    actions = []
    observations = []
    tool_durations = []

    async with websockets.connect(
        ws_url,
        additional_headers={"Cookie": f"openhands_auth={auth_cookie}"},
        max_size=None,
        ping_interval=20,
        ping_timeout=20,
    ) as ws:
        # Handshake
        await ws.recv()
        await ws.send("40")

        timeout_seconds = 180.0
        deadline = time.time() + timeout_seconds

        active_action = None
        action_start = None

        while time.time() < deadline:
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                # Check if all 3 files exist on host
                index_exists = (WORKSPACE_DIR / "index.html").exists()
                css_exists = (WORKSPACE_DIR / "styles.css").exists()
                js_exists = (WORKSPACE_DIR / "app.js").exists()
                if index_exists and css_exists and js_exists and len(actions) > 0:
                    # Give agent a few seconds to finish turn
                    pass
                continue

            if raw_msg == "2":
                await ws.send("3")
                continue

            if not raw_msg.startswith("42"):
                continue

            try:
                payload = json.loads(raw_msg[2:])
                if not (isinstance(payload, list) and len(payload) >= 2 and payload[0] == "oh_event"):
                    continue

                ev = payload[1]
                source = ev.get("source", "")
                action = ev.get("action", "")
                obs = ev.get("observation", "")
                content = ev.get("content", "")
                args = ev.get("args", {})
                ev_id = ev.get("id", "")

                now = time.time()

                if ev_id == "STATUS$RUNTIME_STARTED" and runtime_ready_time is None:
                    runtime_ready_time = now - ws_start
                    print(f"  🐳 Sandbox container ready in {runtime_ready_time:.2f}s")

                if action:
                    actions.append((action, args, now - ws_start))
                    if first_thought_time is None and source == "agent":
                        first_thought_time = now - ws_start
                        print(f"  🧠 First Agent Action/Thought in {first_thought_time:.2f}s: [{action}]")

                    if action in ["run", "execute_bash", "str_replace_editor"]:
                        active_action = action
                        action_start = now
                        cmd_snippet = str(args.get("command", "") or args.get("path", ""))[:60]
                        print(f"  ⚡ Tool Call [{action}]: {cmd_snippet}...")

                if obs:
                    observations.append((obs, str(content)[:80], now - ws_start))
                    if active_action and action_start:
                        dur = now - action_start
                        tool_durations.append((active_action, dur))
                        print(f"  👁️ Tool [{active_action}] finished in {dur:.2f}s (Result: {str(content)[:60]}...)")
                        active_action = None
                        action_start = None

                # Check agent state
                if obs == "agent_state_changed":
                    state = ev.get("extras", {}).get("agent_state")
                    print(f"  🔄 Agent State Changed: {state}")
                    if state in ["awaiting_user_input", "finished"]:
                        print(f"  🏁 Agent completed execution loop!")
                        break

            except json.JSONDecodeError:
                pass

    total_execution_time = time.time() - ws_start
    total_elapsed = time.time() - benchmark_start

    # Step 5: Verification of Generated Webapp on Host
    print("\n[Step 5] Verifying Generated Web Application Files...")
    index_file = WORKSPACE_DIR / "index.html"
    css_file = WORKSPACE_DIR / "styles.css"
    js_file = WORKSPACE_DIR / "app.js"

    assert index_file.exists(), f"Missing index.html at {index_file}"
    assert css_file.exists(), f"Missing styles.css at {css_file}"
    assert js_file.exists(), f"Missing app.js at {js_file}"

    index_size = index_file.stat().st_size
    css_size = css_file.stat().st_size
    js_size = js_file.stat().st_size

    print(f"  ✅ index.html created: {index_size:,} bytes")
    print(f"  ✅ styles.css created: {css_size:,} bytes")
    print(f"  ✅ app.js created:     {js_size:,} bytes")

    # Step 6: Cleanup session
    print("\n[Step 6] Stopping session & initiating sandbox teardown...")
    async with httpx.AsyncClient(base_url=BASE_HTTP, timeout=15.0) as client:
        await client.post(
            f"/api/conversations/{conversation_id}/stop",
            cookies={"openhands_auth": auth_cookie},
        )

    # Detailed Benchmark Timing Summary
    print("\n" + "=" * 72)
    print("📊 BENCHMARK TIMING REPORT: SIMPLE WEBAPP CREATION")
    print("=" * 72)
    print(f"• Target Task:             Create responsive Task Tracker (HTML5 + CSS3 + ES6 JS)")
    print(f"• Active Model:            {model_name}")
    print(f"• Total End-to-End Time:   {total_elapsed:.2f} seconds ({total_elapsed/60:.2f} min)")
    print(f"• Gateway Auth:            {timing['auth_ms']:.1f} ms")
    print(f"• Conversation Creation:   {timing['conv_create_ms']:.1f} ms")
    if runtime_ready_time:
        print(f"• Sandbox Boot & MCP Init: {runtime_ready_time:.2f} s")
    if first_thought_time:
        print(f"• Time to First Action:    {first_thought_time:.2f} s")
    print(f"• Agent Execution Loop:    {total_execution_time:.2f} s")
    print(f"• Total Actions Executed:  {len(actions)}")
    print(f"• Webapp Total Artifacts:  {index_size + css_size + js_size:,} bytes")
    print("=" * 72)

    return {
        "total_elapsed": total_elapsed,
        "auth_ms": timing["auth_ms"],
        "conv_create_ms": timing["conv_create_ms"],
        "runtime_ready_s": runtime_ready_time,
        "first_action_s": first_thought_time,
        "execution_s": total_execution_time,
        "actions_count": len(actions),
        "files": {
            "index.html": index_size,
            "styles.css": css_size,
            "app.js": js_size,
        },
    }


if __name__ == "__main__":
    asyncio.run(run_benchmark())
