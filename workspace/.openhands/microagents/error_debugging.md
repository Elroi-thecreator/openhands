---
name: error_debugging
type: knowledge
version: 1.1.0
agent: CodeActAgent
triggers:
  - error
  - fix
  - debug
  - failed
  - exception
  - traceback
  - issue
---

# Systematic Error Diagnosis & Antigravity Recovery Protocol

When encountering any error, non-zero exit code, or failure:

## 1. Strictly Avoid Loop Repetition
- NEVER execute the exact same failing command twice with identical arguments.
- Repeating a failing action causes `AgentStuckInLoopError` and terminates the session.

## 2. Run Autonomous Diagnosis (`diagnose_error`)
- Instead of manually guessing lines or blind editing, invoke the Antigravity diagnostic engine:
  ```bash
  diagnose_error --file <failing_file> --line <line_number>
  ```
  Or pass the raw error string/traceback:
  ```bash
  diagnose_error --traceback "<traceback_string>"
  ```
- To test missing dependencies or blocked ports:
  ```bash
  diagnose_error --check-import <module_name>
  diagnose_error --check-port <port_number>
  ```

## 3. Manage Process Hangs & Timeouts (`manage_task`)
- If a command hit a timeout (`exit_code: -1`) or is hanging:
  ```bash
  manage_task logs <task_id>
  manage_task send_input <task_id> --input "y\n"
  manage_task kill <task_id>
  ```

## 4. Human-in-the-Loop Escalation (`escalate_error`)
- If the error is caused by ambiguous business logic, missing third-party keys, or architectural fork:
  ```bash
  escalate_error --error "<summary of issue>" --context "<current action>"
  ```
  This immediately triggers a structured Decision Card in the user's browser with a safe default timeout.

## 5. API Rate-Limit & Quota Recovery (`model_failover`)
- If cloud LLM requests fail with HTTP 429, quota exhaustion, or rate limits:
  ```bash
  model_failover --to local
  ```
  This automatically swaps inference to local zero-cost Ollama `qwen2.5-coder:1.5b`.

## 6. Verify Before Declaring Fixed
- Re-run only the specific reproduction command or unit test to prove resolution.
- Verify no secondary syntax errors exist via `diagnose_error --file <modified_file>`.

