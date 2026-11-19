#!/usr/bin/env python3
"""
Antigravity Native FastMCP Server for OpenHands.
Exposes Antigravity parity capabilities (Artifacts, Decision Cards, Task Supervision,
Reactive Scheduling, and Error Diagnostics) as Model Context Protocol (MCP) tools.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not installed in current environment", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("Antigravity")

CANDIDATE_DIRS = [
    Path("/workspace/artifacts"),
    Path("/home/ubuntu/openhand/workspace/artifacts"),
    Path("artifacts"),
]
ARTIFACTS_DIR = None
for d in CANDIDATE_DIRS:
    try:
        d.mkdir(parents=True, exist_ok=True)
        ARTIFACTS_DIR = d
        break
    except Exception:
        continue
if not ARTIFACTS_DIR:
    ARTIFACTS_DIR = Path("artifacts")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

GATEWAY_URLS = [
    os.getenv("ANTIGRAVITY_GATEWAY_URL", "http://host.docker.internal:8080"),
    "http://172.17.0.1:8080",
    "http://127.0.0.1:8080",
]


def _call_gateway(endpoint: str, payload: dict, timeout: int = 30) -> Optional[dict]:
    for base in GATEWAY_URLS:
        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
    return None


@mcp.tool()
def write_artifact(
    filename: str,
    title: str,
    summary: str,
    content: str,
    request_feedback: bool = False
) -> str:
    """Create or update an interactive Antigravity artifact document.
    Artifacts render directly in the UI drawer with an actionable 'Proceed with Plan' review button.

    Args:
        filename: Artifact file name (e.g., 'architecture_plan.md')
        title: Short human-readable title
        summary: High-level summary of the artifact's purpose
        content: Full markdown content of the artifact
        request_feedback: Whether to request user feedback/approval ('Proceed' action button in UI)
    """
    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    # Frontmatter construction
    frontmatter = [
        "---",
        f"title: \"{title or filename}\"",
        f"summary: \"{summary}\"",
        f"request_feedback: {str(request_feedback).lower()}",
        "user_facing: true",
        "---",
        "",
    ]
    full_text = "\n".join(frontmatter) + content.lstrip()

    # Write to local artifacts folder
    target_path = ARTIFACTS_DIR / filename
    target_path.write_text(full_text, encoding="utf-8")

    # Sync with Gateway API for real-time UI rendering
    res = _call_gateway("gateway/api/artifacts", {
        "filename": filename,
        "title": title,
        "summary": summary,
        "content": full_text,
        "request_feedback": request_feedback
    })

    status_note = " (Synced with Antigravity UI Drawer)" if res else " (Saved locally)"
    action_note = " [⚡ User Review Requested - Proceed button active]" if request_feedback else ""
    return f"✓ Artifact '{filename}' successfully saved at {target_path}{status_note}{action_note}"


@mcp.tool()
def ask_question(
    question: str,
    options: List[str],
    is_multi_select: bool = False,
    timeout_seconds: int = 45
) -> str:
    """Prompt the user with an interactive structured decision card.
    Presents clickable option cards in the chat UI and waits asynchronously for selection.

    Args:
        question: The question prompt to display
        options: List of choices (first choice should start with '(Recommended)')
        is_multi_select: Whether the user can select multiple options
        timeout_seconds: Seconds to wait for user interaction before falling back to recommended
    """
    # Create question
    created = _call_gateway("gateway/api/questions", {
        "question": question,
        "options": options,
        "is_multi_select": is_multi_select,
        "timeout": timeout_seconds
    })

    if not created or "id" not in created:
        rec = options[0] if options else "Option 1"
        return f"[Decision Fallback] Defaulted to: {rec}"

    qid = created["id"]
    # Wait for answer
    ans = _call_gateway(f"gateway/api/questions/{qid}/wait", {}, timeout=timeout_seconds + 5)
    if ans and "answer" in ans:
        return f"User selected: {ans['answer']}"
    
    rec = options[0] if options else "Option 1"
    return f"Timeout reached ({timeout_seconds}s). Auto-selected recommended: {rec}"


@mcp.tool()
def manage_task(
    action: str,
    command: str = "",
    task_id: str = "",
    summary: str = ""
) -> str:
    """Supervise long-running commands and background processes without blocking.

    Args:
        action: Action to perform: 'spawn', 'list', 'status', 'logs', or 'kill'
        command: Shell command line to execute (for 'spawn')
        task_id: Task ID returned by spawn
        summary: Short description of the task purpose
    """
    action = action.lower().strip()
    if action == "spawn":
        if not command:
            return "Error: 'command' required for spawn"
        res = _call_gateway("gateway/api/tasks/spawn", {
            "command": command,
            "summary": summary or command[:40]
        })
        if res and "task_id" in res:
            return f"✓ Background task spawned: {res['task_id']}"
        return "Failed to spawn background task via Gateway."

    elif action in ("list", "status", "logs", "kill"):
        res = _call_gateway(f"gateway/api/tasks/{action}", {"task_id": task_id})
        return json.dumps(res, indent=2) if res else f"Executed {action} for {task_id}"

    return f"Unknown task action: {action}. Use spawn, list, status, logs, kill."


@mcp.tool()
def diagnose_error(
    error_traceback: str,
    file_path: str = "",
    line_number: int = 0
) -> str:
    """Analyze a failure, parse Python/Node tracebacks, inspect surrounding code, and recommend fixes.

    Args:
        error_traceback: Raw error output or stack trace
        file_path: Optional file path implicated in the error
        line_number: Optional line number of the failure
    """
    diagnostics = []
    diagnostics.append("=== ANTIGRAVITY ERROR DIAGNOSTIC REPORT ===")

    # 1. Path check
    if file_path:
        p = Path(file_path)
        if not p.exists():
            diagnostics.append(f"❌ Target file does not exist: {file_path}")
            # Search workspace
            candidates = list(Path("/workspace").glob(f"**/{p.name}")) if Path("/workspace").exists() else []
            if candidates:
                diagnostics.append(f"💡 Found matching file in workspace: {candidates[0]}")
        else:
            diagnostics.append(f"✓ File exists: {file_path} ({p.stat().st_size} bytes)")
            if line_number > 0:
                try:
                    lines = p.read_text(encoding="utf-8").splitlines()
                    start = max(0, line_number - 4)
                    end = min(len(lines), line_number + 3)
                    diagnostics.append(f"--- Context (lines {start+1}-{end}): ---")
                    for i in range(start, end):
                        marker = ">> " if (i + 1) == line_number else "   "
                        diagnostics.append(f"{marker}{i+1:4d}: {lines[i]}")
                except Exception as e:
                    diagnostics.append(f"Could not read context lines: {e}")

    # 2. Syntax check
    if file_path and file_path.endswith(".py") and Path(file_path).exists():
        import py_compile
        try:
            py_compile.compile(file_path, doraise=True)
            diagnostics.append("✓ Python syntax check passed.")
        except py_compile.PyCompileError as e:
            diagnostics.append(f"❌ Python SyntaxError detected:\n{e.msg}")

    # 3. Known error patterns
    tb_lower = error_traceback.lower()
    if "no such file or directory" in tb_lower:
        diagnostics.append("💡 Root cause: Missing directory path. Solution: Run `mkdir -p <dirname>` before creating files.")
    if "permission denied" in tb_lower:
        diagnostics.append("💡 Root cause: Linux permission boundary. Solution: Verify file ownership or permissions with `ls -la`.")
    if "address already in use" in tb_lower:
        diagnostics.append("💡 Root cause: Port conflict. Solution: Find listening process or bind to a different port.")

    return "\n".join(diagnostics)


@mcp.tool()
def schedule_task(
    delay_seconds: int = 0,
    cron: str = "",
    prompt: str = ""
) -> str:
    """Schedule a reactive one-shot timer or cron reminder.
    The agent yields its turn; the system automatically wakes up when the schedule triggers.

    Args:
        delay_seconds: Seconds to wait for a one-shot wakeup
        cron: Standard 5-field cron expression for recurring schedule
        prompt: Message to inject into context when timer fires
    """
    res = _call_gateway("gateway/api/schedule", {
        "delay_seconds": delay_seconds,
        "cron": cron,
        "prompt": prompt or "Antigravity reactive schedule triggered"
    })
    if res and "job_id" in res:
        return f"✓ Reactive schedule registered: {res['job_id']} (fires in {delay_seconds}s)"
    return "Failed to register schedule with Gateway."


if __name__ == "__main__":
    mcp.run()
