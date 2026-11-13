---
name: webapp_architecture
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - webapp
  - calculator
  - web app
  - dashboard
  - frontend
  - backend
  - flask
  - fastapi
---

# Web Application Development Standards (Antigravity Style)

When asked to create a web application or service:

## 1. Project Structure
Organize the app cleanly in a dedicated directory under `/workspace/<app_name>`:
```text
/workspace/<app_name>/
├── app.py (or main.py)
├── requirements.txt
├── templates/
│   └── index.html
└── static/
    ├── css/
    └── js/
```

## 2. Modern UI Standards
- Use modern, responsive styling (Tailwind CSS via CDN or clean CSS).
- Include clear headings, intuitive forms, interactive calculation/results sections, and responsive mobile-ready layouts.
- Add input validation and clear feedback on UI actions.

## 3. Server Configuration
- Bind servers to `0.0.0.0` with an available port (e.g., `5000`, `8000`, or dynamic) so the app can be reached both inside the container and via port mapping.
- Background the server using `python app.py > server.log 2>&1 &` so the command returns immediately and does not hang your tool turn.

## 4. Verification
- Verify server startup by checking the log: `sleep 2 && cat server.log`.
- Test the endpoint locally: `curl -I http://127.0.0.1:<port>/`.
- Report the local port and files to the user.
