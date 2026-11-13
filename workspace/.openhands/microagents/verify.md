---
name: verify
type: task
version: 1.0.0
agent: CodeActAgent
triggers:
  - /verify
inputs:
  - name: target
    description: "The component or application to verify"
---

# Antigravity Verification Suite (/verify)

When the user triggers `/verify`:
1. **Syntax Check**: Run `python3 -m py_compile` or `node --check` on all source files.
2. **Dependency Audit**: Verify all packages in `requirements.txt` or `package.json` are installed.
3. **Execution Test**: Start the service or run the test suite (e.g. `pytest` or `npm test`).
4. **Log Inspection**: Capture stdout/stderr and check for unhandled exceptions or warnings.
5. **Report**: Summarize results in a clear pass/fail markdown table.
