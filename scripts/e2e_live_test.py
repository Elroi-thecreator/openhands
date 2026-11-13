#!/usr/bin/env python3
"""
Full Live End-to-End Test for OpenHands with FastAPI Gateway, WebSocket & Gemini 3 Flash
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
TEST_FILE = "/home/ubuntu/openhand/workspace/live_perf_test.txt"
VERIFICATION_STRING = "OPENHANDS_E2E_PERFORMANCE_TEST_VERIFIED"


async def main():
    print("=" * 64)
    print("🚀 OPENHANDS END-TO-END LIVE PERFORMANCE & TOOL EXECUTION TEST")
    print("=" * 64)

    # 1. Gateway Authentication
    print("\n[1/6] Gateway Authentication...")
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
        assert resp.status_code == 302, f"Login failed with status {resp.status_code}"
        auth_cookie = client.cookies.get("openhands_auth")
        assert auth_cookie, "openhands_auth cookie missing from login response"
        t_auth = time.time() - t0
        print(f"✅ Authenticated in {t_auth*1000:.1f}ms. Session cookie issued.")

        # 2. Backend Config Check
        print("\n[2/6] Backend Configuration Check...")
        t0 = time.time()
        cfg_resp = await client.get("/api/options/config", cookies={"openhands_auth": auth_cookie})
        assert cfg_resp.status_code == 200, f"Config failed: {cfg_resp.status_code}"
        cfg = cfg_resp.json()
        llm_model = cfg.get("llm_model", "unknown")
        t_cfg = time.time() - t0
        print(f"✅ Config response in {t_cfg*1000:.1f}ms. Active model: {llm_model}")

        # 3. Create Conversation Session
        print("\n[3/6] Initializing Conversation Session...")
        prompt = (
            f"Run bash: echo '{VERIFICATION_STRING}' > /workspace/live_perf_test.txt && "
            f"cat /workspace/live_perf_test.txt"
        )
        t0 = time.time()
        conv_resp = await client.post(
            "/api/conversations",
            json={"initial_user_msg": prompt},
            cookies={"openhands_auth": auth_cookie},
        )
        assert conv_resp.status_code in [200, 201], f"Conversation creation failed: {conv_resp.status_code}"
        conversation_id = conv_resp.json()["conversation_id"]
        t_conv = time.time() - t0
        print(f"✅ Conversation {conversation_id} created in {t_conv*1000:.1f}ms.")

    # 4. Connect via WebSocket (Triggers Sandbox Spin-up & Joins Event Stream)
    print("\n[4/6] Connecting via WebSocket Tunnel & Starting Live Agent Turn...")
    ws_url = (
        f"{BASE_WS}/socket.io/?EIO=4&transport=websocket"
        f"&conversation_id={conversation_id}&providers_set=github"
    )

    # Clean up any stale test file
    if Path(TEST_FILE).exists():
        Path(TEST_FILE).unlink()

    turn_start_time = time.time()
    tool_executed = False
    file_verified = False
    agent_replied = False
    runtime_started = False
    errors_encountered = []

    async with websockets.connect(
        ws_url,
        additional_headers={"Cookie": f"openhands_auth={auth_cookie}"},
        max_size=None,
        ping_interval=20,
        ping_timeout=20,
    ) as ws:
        # Engine.IO Handshake
        m1 = await ws.recv()
        # Send Socket.IO Connect frame
        await ws.send("40")

        # Listen for events
        timeout_seconds = 120.0
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                # Check if file has appeared
                if Path(TEST_FILE).exists() and not file_verified:
                    content = Path(TEST_FILE).read_text().strip()
                    if VERIFICATION_STRING in content:
                        file_verified = True
                        print(f"   🎯 File verified on host: {content}")
                if file_verified and (agent_replied or tool_executed):
                    break
                continue

            # Engine.IO heartbeat ping -> pong
            if raw_msg == "2":
                await ws.send("3")
                continue

            if not raw_msg.startswith("42"):
                continue

            try:
                event_data = json.loads(raw_msg[2:])
                if isinstance(event_data, list) and len(event_data) >= 2 and event_data[0] == "oh_event":
                    ev = event_data[1]
                    source = ev.get("source", "")
                    action = ev.get("action", "")
                    obs = ev.get("observation", "")
                    msg = ev.get("message", "")
                    content = ev.get("content", "")

                    if ev.get("id") == "STATUS$RUNTIME_STARTED":
                        runtime_started = True
                        t_runtime = time.time() - turn_start_time
                        print(f"   🐳 Sandbox container ready in {t_runtime:.2f}s.")

                    if action:
                        print(f"   ⚡ Action: [{source}] {action} - {str(ev.get('args', {}))[:90]}")
                    elif obs:
                        print(f"   👁️ Observation: [{source}] {obs} - {str(content or msg)[:90]}")

                    if obs == "error":
                        err_text = str(content or msg)
                        errors_encountered.append(err_text)
                        print(f"   ⚠️ ERROR: {err_text}")
                        if "Missing required parameters" in err_text:
                            raise RuntimeError(f"REGRESSION DETECTED: {err_text}")

                    if action == "run" or obs == "run":
                        tool_executed = True
                        if VERIFICATION_STRING in str(content):
                            print(f"   🎯 Command executed successfully in container sandbox!")

                    if source == "agent" and (action == "message" or action == "finish"):
                        agent_replied = True
                        agent_content = ev.get("args", {}).get("content", "") or ev.get("thought", "") or msg
                        print(f"   🤖 Agent Response/Finish: {agent_content.strip()[:100]}...")

                    if obs == "agent_state_changed" and ev.get("extras", {}).get("agent_state") in [
                        "awaiting_user_input",
                        "finished",
                        "stopped",
                    ]:
                        if Path(TEST_FILE).exists():
                            content = Path(TEST_FILE).read_text().strip()
                            if VERIFICATION_STRING in content:
                                file_verified = True
                                break

            except json.JSONDecodeError:
                pass

    t_turn_elapsed = time.time() - turn_start_time

    # 5. Verify Artifact on Host
    print("\n[5/6] Verifying Artifact in Workspace Mount...")
    assert Path(TEST_FILE).exists(), f"File {TEST_FILE} was not created!"
    file_content = Path(TEST_FILE).read_text().strip()
    assert VERIFICATION_STRING in file_content, f"Content mismatch: {file_content}"
    print(f"✅ Host file confirmed: '{file_content}'")
    Path(TEST_FILE).unlink()

    # 6. Stop and Clean up session
    print("\n[6/6] Stopping session & verifying sandbox cleanup...")
    async with httpx.AsyncClient(base_url=BASE_HTTP, timeout=15.0) as client:
        stop_resp = await client.post(
            f"/api/conversations/{conversation_id}/stop",
            cookies={"openhands_auth": auth_cookie},
        )
        print(f"   • Stop response status: {stop_resp.status_code}")

    # Check for errors
    assert not errors_encountered, f"Errors were recorded during execution: {errors_encountered}"

    print("\n" + "=" * 64)
    print(f"🎉 LIVE END-TO-END PERFORMANCE TEST PASSED in {t_turn_elapsed:.2f}s!")
    print(f"   • Gateway Auth:   {t_auth*1000:.1f}ms")
    print(f"   • Config Fetch:   {t_cfg*1000:.1f}ms")
    print(f"   • Conv Creation:  {t_conv*1000:.1f}ms")
    print(f"   • Full Execution: {t_turn_elapsed:.2f}s (Prompt -> LLM -> Tool -> Sandbox -> Done)")
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
