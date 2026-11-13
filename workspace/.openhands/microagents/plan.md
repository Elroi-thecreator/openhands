---
name: plan
type: task
version: 1.0.0
agent: CodeActAgent
triggers:
  - /plan
inputs:
  - name: task
    description: "The task to create an implementation plan for"
---

# Antigravity Implementation Planner (/plan)

When the user triggers `/plan`:
1. **Analyze Requirements**: Thoroughly review user specifications, constraints, and dependencies.
2. **Decompose into Steps**: Create a sequential, numbered roadmap with verifiable milestones.
3. **Identify Files**: List every file to be created, modified, or tested.
4. **Draft Architecture Artifact**: Save the blueprint as a markdown document in `/workspace/artifacts/plan_<topic>.md`.
5. **Present to User**: Provide a concise summary and ask for confirmation before executing.
