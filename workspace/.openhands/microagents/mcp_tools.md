---
name: mcp_tools
type: repo
version: 1.0.0
agent: CodeActAgent
mcp_tools:
  stdio_servers:
    - name: github
      command: /usr/local/bin/npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    - name: fetch
      command: /openhands/bin/uvx
      args: ["mcp-server-fetch"]
      env: {}
    - name: time
      command: /openhands/bin/uvx
      args: ["mcp-server-time"]
      env: {}
    - name: memory
      command: /usr/local/bin/npx
      args: ["-y", "@modelcontextprotocol/server-memory"]
      env: {}
    - name: antigravity
      command: /openhands/poetry/openhands-ai-5O4_aCHf-py3.12/bin/python
      args: ["/workspace/bin/antigravity_mcp.py"]
      env:
        ANTIGRAVITY_GATEWAY_URL: "http://host.docker.internal:8080"
---
# Model Context Protocol (MCP) Priority Protocol

Whenever an MCP tool is available for an operation, you MUST prioritize the MCP tool over raw bash scripts, curl invocations, or terminal workarounds.

## 1. GitHub Operations (`github` MCP)
- **Pull Requests**: Use `create_pull_request`, `get_pull_request`, `list_pull_requests` instead of raw git CLI or gh commands.
- **Repository Exploration & Search**: Use `search_repositories` and `search_code` for targeted GitHub exploration.
- **Issues & Tracking**: Use `create_issue`, `get_issue`, `list_issues`, and `add_issue_comment`.
- **Direct File Operations**: Use `get_file_contents` and `create_or_update_file` when interacting with remote branches.

## 2. Web Documentation & Content Ingestion (`fetch` MCP)
- NEVER run `curl <url>` or `wget <url>` to read external documentation or web content. Raw HTML causes prompt bloating and token exhaustion.
- Always use `fetch(url)` which parses web content into clean, readable Markdown directly.

## 3. Persistent Knowledge Graph (`memory` MCP)
- Use MCP Memory (`create_entities`, `create_relations`, `read_graph`, `search_nodes`) to retain critical user preferences, architectural invariants, and debugging insights across sessions.

## 4. Accurate Timekeeping & Scheduling (`time` MCP)
- Use MCP Time (`get_current_time`, `convert_time`) for timestamps, scheduled delay calculations, and UTC synchronization instead of guessing or executing bash `date`.

## 5. Native Antigravity Artifacts & Diagnostics (`antigravity` MCP)
- Call `write_artifact`, `ask_question`, `manage_task`, `diagnose_error`, and `schedule_task` directly via MCP function calling.
