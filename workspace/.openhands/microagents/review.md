---
name: review
type: task
version: 1.0.0
agent: CodeActAgent
triggers:
  - /review
inputs:
  - name: code
    description: "The code or directory to review"
---

# Antigravity Code Reviewer (/review)

When the user triggers `/review`:
1. **Security Audit**: Check for exposed credentials, injection vulnerabilities, and unrestricted endpoints.
2. **Performance Audit**: Check for blocking operations, unindexed lookups, or high memory allocations.
3. **Architecture Standard**: Verify code aligns with project standards in `/workspace/knowledge/`.
4. **Actionable Recommendations**: Provide prioritized suggestions (High / Medium / Low).
