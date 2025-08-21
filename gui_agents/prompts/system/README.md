# Prompt Management (One File per Tool + Dynamic Assembly Documentation)

This directory stores the system prompts for each tool as plain-text `.txt` files, making them easy to edit and version-control.

- Naming convention: Filename equals tool name, e.g., `action_generator.txt`, `subtask_planner.txt`, `fast_action_generator.txt`.
- Scope: These `.txt` files are used as system prompts. The user messages are dynamically assembled in the application code (see below).
- Location: `lybicguiagents/gui_agents/prompts/`

Supported tools and files:

- `action_generator.txt`
- `action_generator_with_takeover.txt`
- `fast_action_generator.txt`
- `fast_action_generator_with_takeover.txt`
- `subtask_planner.txt`
- `dag_translator.txt`
- `traj_reflector.txt`
- `grounding.txt`
- `evaluator.txt`
- `context_fusion.txt`
- `query_formulator.txt`
- `narrative_summarization.txt`
- `episode_summarization.txt`

---

## Dynamic Assembly Overview (where and what is assembled)

All paths referenced here are under `lybicguiagents/gui_agents/`.

### 1) Task Planning (Subtask Planner)

- Location: `agents/manager.py::_generate_step_by_step_plan`
- Scenarios: Initial planning / re-planning
- Dynamic content:
  - On the first turn (`turn_count == 0`), RAG runs:
    - `formulate_query(instruction, observation)` → produces `search_query`
    - `retrieve_narrative_experience(instruction)` → similar historical tasks
    - (Optional) `retrieve_knowledge(...)` → web knowledge via search engine
    - `knowledge_fusion(...)` → integrated knowledge
    - The integrated knowledge is appended to instruction text:
      - `instruction += "\nYou may refer to some retrieved knowledge..." + integrated_knowledge`
    - Prefix: `prefix_message = f"TASK_DESCRIPTION is {instruction}"`
  - Based on context, `generator_message` is built as one of:
    - Re-plan on failure: includes completed/future subtasks and `agent_log`
    - Revise on subtask completion: similar
    - Initial planning: `Please generate the initial plan for the task.`
  - Final input to `subtask_planner`: `prefix_message + "\n" + generator_message`

Example (initial planning):

```bash
TASK_DESCRIPTION is <instruction with integrated knowledge>

Please generate the initial plan for the task.
```

### 2) DAG Generation (DAG Translator)

- Location: `agents/manager.py::_generate_dag`
- Dynamic content:
  - Input is wrapped as: `Instruction: {instruction}\nPlan: {plan}` for `dag_translator`

Example:

```bash
Instruction: <goal/knowledge-augmented instruction>
Plan: <planner output>
```

### 3) Executor (Action Generator)

- Location: `agents/worker.py::generate_next_action`
- First turn:
  - Optional RAG: `retrieve_episodic_experience(subtask_query_key)`; append “similar subtask + experience” into `Tu`
  - One-time prefix injection:
    - `SUBTASK_DESCRIPTION is {subtask}`
    - `TASK_DESCRIPTION is {Tu}` (may include episodic experience)
    - `FUTURE_TASKS is {a,b,c}`
    - `DONE_TASKS is {x,y}`
- Subsequent turns:
  - `Your previous action was: {latest_action}`
  - Optional `reflection`
  - Aggregated `agent_log`
- Final input to `action_generator` (or `_with_takeover`) is the assembled text as `str_input`.

Example (first turn):

```bash
SUBTASK_DESCRIPTION is Rename the file

TASK_DESCRIPTION is <task + optional similar subtask experience>

FUTURE_TASKS is Open folder, Upload file

DONE_TASKS is Download file
```

### 4) Direct Execution (Fast Action Generator)

- Location: `agents/agent_s.py::AgentSFast.predict`
- Dynamic content:
  - First message: `Task Description: {instruction}` + “The initial screen is provided...”
  - Later turns: add `agent_log` (and optional `reflection`) to the message
- Final input to `fast_action_generator` (or `_with_takeover`) is the assembled text as `str_input`.

Example:

```bash
Task Description: <instruction>

Please refer to the agent log to understand the progress and context of the task so far.
<expanded agent_log>
```

### 5) Visual Grounding (Coordinate Generation)

- Location: `agents/grounding.py::Grounding.generate_coords`
- Dynamic content:
  - A strict instruction string defining the coordinate-only output format is hard-coded in the function and sent with `ref_expr` + screenshot to the `grounding` tool.
  - Output must be a single coordinate pair `(x, y)` with no extra text.

Note: This prompt is currently hard-coded in the function (not loaded from `.txt`). Modify that string if you need to change the behavior.

### 6) Web Search Augmentation

- Location: `tools/tools.py::ActionGeneratorTool.execute` and `FastActionGeneratorTool.execute`
- Dynamic content (when `enable_search=true`):
  - Before calling the LLM, `str_input` is wrapped as:
    - `[Action Request]\n{original}\n[End of Action Request]`
    - appended with search results: `[Web Search Results for '{original}']\n{search_results}\n[End of Web Search Results]`

### 7) Summarization (Narrative / Episode)

- Location: `agents/manager.py::summarize_narrative` and `summarize_episode`
- Dynamic content:
  - The full trajectory text is passed as `str_input` with minimal additional formatting.

---

## Placeholders and Variables

- Placeholders appearing in `.txt` system prompts (e.g., `SUBTASK_DESCRIPTION`, `TASK_DESCRIPTION`, `FUTURE_TASKS`, `DONE_TASKS`, `INSTRUCTION`) are not string-replaced inside the system prompt. Their actual values are provided via the dynamically assembled user message (see examples above).
- `CURRENT_OS` may appear in system prompts as conceptual guidance. There is no explicit string replacement; runtime platform context is conveyed through the assembled user message and the screenshot.

---

## How to Modify Prompts

- Change long-lived rules/format/style: edit the corresponding `.txt` system prompt directly.
- Change runtime assembly logic: update the relevant code:
  - Planning: `agents/manager.py::_generate_step_by_step_plan`
  - DAG generation: `agents/manager.py::_generate_dag`
  - Execution: `agents/worker.py::generate_next_action`
  - Direct execution: `agents/agent_s.py::AgentSFast.predict`
  - Visual grounding format rule: `agents/grounding.py::Grounding.generate_coords`
  - Search augmentation wrappers: `gui_agents/tools/tools.py` in `ActionGeneratorTool` and `FastActionGeneratorTool`

---

## Adding a New Tool Prompt

1) Add a `.txt` file in this directory named exactly after the tool.
2) Ensure `ToolFactory` in `tools.py` maps the tool name.
3) Register and invoke the tool in the application code as needed.
