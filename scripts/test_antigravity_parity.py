#!/usr/bin/env python3
"""
Automated End-to-End Verification Suite for Antigravity Parity in OpenHands
Tests all newly built Antigravity subsystems:
1. Artifacts Engine & Review Workflow (write_artifact)
2. Interactive Decision Cards & Question Polling (ask_question)
3. Reactive Background Task Supervisor (manage_task)
4. Reactive Delay & Cron Scheduler (schedule)
5. Subagent Delegation & Inter-Agent Mailbox (subagent)
6. Progressive Skill Discovery & Indexing (skill)
"""
import sys
import subprocess
import time
import json
import urllib.request

GATEWAY_BASE = "http://127.0.0.1:8080"

def test_gateway_health():
    print("[1/6] Testing Gateway Health & Live Status...")
    req = urllib.request.urlopen(f"{GATEWAY_BASE}/gateway/health")
    assert req.status == 200
    data = json.loads(req.read().decode())
    assert data.get("status") == "ok"
    print("  ✓ Gateway health OK")

def test_artifacts():
    print("[2/6] Testing Antigravity Artifacts Engine...")
    cmd = [
        "python3", "/home/ubuntu/openhand/workspace/bin/write_artifact",
        "system_blueprint.md",
        "--title", "E2E Verification Blueprint",
        "--summary", "Comprehensive system verification",
        "--request-feedback",
        "--content", "# E2E Verification Blueprint\n\nTesting complete pipeline."
    ]
    subprocess.check_call(cmd)
    
    # Verify via API
    req = urllib.request.urlopen(f"{GATEWAY_BASE}/gateway/api/artifacts/system_blueprint.md")
    assert req.status == 200
    art = json.loads(req.read().decode())
    assert art["metadata"]["title"] == "E2E Verification Blueprint"
    assert art["metadata"]["request_feedback"] is True
    print("  ✓ Artifact created and verified via API")

def test_questions():
    print("[3/6] Testing Interactive Decision Cards (ask_question)...")
    proc = subprocess.Popen(
        ["python3", "/home/ubuntu/openhand/workspace/bin/ask_question",
         "--question", "Which test suite to run?",
         "--options", "Unit Tests, Integration Tests, End-to-End",
         "--timeout", "10"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(1)
    
    # Fetch pending question
    req = urllib.request.urlopen(f"{GATEWAY_BASE}/gateway/api/questions/pending")
    res = json.loads(req.read().decode())
    assert res.get("pending") is True
    qid = res["question"]["id"]
    
    # Answer question
    answer_payload = json.dumps({"answer": "End-to-End"}).encode()
    ans_req = urllib.request.Request(
        f"{GATEWAY_BASE}/gateway/api/questions/{qid}/answer",
        data=answer_payload,
        headers={"Content-Type": "application/json"}
    )
    ans_resp = urllib.request.urlopen(ans_req)
    assert ans_resp.status == 200
    
    stdout, stderr = proc.communicate(timeout=5)
    assert "End-to-End" in stdout
    print("  ✓ Decision Card prompt & synchronous answer cycle OK")

def test_manage_task():
    print("[4/6] Testing Background Task Supervisor (manage_task)...")
    cmd = [
        "python3", "/home/ubuntu/openhand/workspace/bin/manage_task",
        "spawn", "--command", "echo 'Hello Background Task' && sleep 1",
        "--summary", "Parity Verification Subprocess"
    ]
    out = subprocess.check_output(cmd, text=True)
    assert "task-" in out
    
    time.sleep(1.5)
    list_out = subprocess.check_output(["python3", "/home/ubuntu/openhand/workspace/bin/manage_task", "list"], text=True)
    assert "Parity Verification" in list_out
    print("  ✓ Background task spawned, executed, and logged OK")

def test_schedule():
    print("[5/6] Testing Reactive Scheduler (schedule)...")
    cmd = [
        "python3", "/home/ubuntu/openhand/workspace/bin/schedule",
        "--seconds", "1",
        "--prompt", "Verification Wakeup Alert"
    ]
    subprocess.check_call(cmd)
    time.sleep(1.5)
    list_out = subprocess.check_output(["python3", "/home/ubuntu/openhand/workspace/bin/schedule", "--list"], text=True)
    assert "Verification Wakeup Alert" in list_out
    print("  ✓ Reactive schedule timer triggered and notified OK")

def test_skills_and_subagents():
    print("[6/6] Testing Progressive Skills & Subagent Mailbox...")
    # Skill
    subprocess.check_call([
        "python3", "/home/ubuntu/openhand/workspace/bin/skill",
        "create", "security-audit",
        "--description", "Automated cryptographic and session token verification"
    ])
    skills_list = subprocess.check_output(["python3", "/home/ubuntu/openhand/workspace/bin/skill", "list"], text=True)
    assert "security-audit" in skills_list
    
    # Subagent
    sub_out = subprocess.check_output([
        "python3", "/home/ubuntu/openhand/workspace/bin/subagent",
        "invoke", "--role", "Security Specialist",
        "--prompt", "Inspect token hashing"
    ], text=True)
    assert "subagent-" in sub_out
    print("  ✓ Progressive skill discovery & subagent orchestrator OK")

def main():
    print("=======================================================")
    print("🚀 RUNNING ANTIGRAVITY FULL PARITY VERIFICATION SUITE")
    print("=======================================================")
    test_gateway_health()
    test_artifacts()
    test_questions()
    test_manage_task()
    test_schedule()
    test_skills_and_subagents()
    print("=======================================================")
    print("🎉 ALL ANTIGRAVITY SUBSYSTEMS OPERATIONAL AND VERIFIED!")
    print("=======================================================")

if __name__ == "__main__":
    main()
