---
name: plan
type: task
version: 1.1.0
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
4. **Draft Architecture Artifact**:
   - Save the blueprint using the Antigravity tool:
     ```bash
     cat << 'EOF' | write_artifact plan_<topic>.md --title "<Title>" --summary "<Summary>" --request-feedback
     # <Title>
     ...
     EOF
     ```
   - This automatically registers the plan with the Antigravity Artifacts Engine, rendering it in the UI and presenting the user with a glowing **"⚡ Proceed with Plan"** approval button.
5. **Ask User Clarifications if Needed**:
   - If design or architecture alternatives exist, use `ask_question`:
     ```bash
     ask_question --question "Which pattern do you prefer?" --options "(Recommended) Option A, Option B"
     ```
6. **Present Summary**: Provide a concise summary and point the user to the active artifact drawer.
