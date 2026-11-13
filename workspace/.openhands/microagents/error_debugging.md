---
name: error_debugging
type: knowledge
version: 1.0.0
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

# Systematic Error Diagnosis & Loop Avoidance

When encountering any error or bug:

## 1. Never Repeat the Exact Same Failing Action
- Repeating the identical tool call that just failed will trigger `AgentStuckInLoopError` and terminate the session.
- Always change your arguments, check prerequisites, or investigate the underlying state before re-running.

## 2. Diagnose Before Modifying
- Read the full traceback or stderr output carefully.
- Inspect the offending file and line number:
  - Use `head`, `tail`, or `cat` to see the context around the error.
  - Check imports and package versions (`pip list`, `node -v`).

## 3. Verify Fix
- After applying a fix, re-run only the test or command that reproduces the issue to confirm resolution.
- Ensure no secondary regressions were introduced.
