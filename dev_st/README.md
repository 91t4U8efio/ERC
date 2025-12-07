# ERC3 Benchmark Agent: Tri-Agent
"Code-First" Architecture

This repository contains the definitive submission for the ERC3-DEV and ERC3-TEST
benchmarks. It implements a sophisticated Tri-Agent Architecture that fundamentally
reimagines how autonomous agents interact with complex enterprise environments. By
leveraging Active RAG (Retrieval Augmented Generation) and Python Code Execution, this
system overcomes the limitations of traditional, linear tool-calling agents to solve multi-step
business tasks with high precision.

## 🏗 Architecture: A Symphony of Specialized Agents

Unlike standard "Tool Calling" agents that simply output static JSON requests one at a time,
this system utilizes a Code Agent paradigm. The cognitive load is distributed across three
highly specialized agents, each designed to handle a specific dimension of the problem
space: Knowledge, Planning, and Execution.

### 1. The WikiAgent ("The Researcher")

- **Role**: Active Knowledge Retrieval & Context Injection.
- **Behavior**: This agent runs asynchronously before the main execution loop begins. It
acts as the "pre-frontal cortex," gathering the necessary context before any action is
taken.
- **The "Active RAG" Process**:
  1. **Semantic Analysis**: It first analyzes the raw user task (e.g., "Update Felix's salary")
to extract high-value search keywords (e.g., "salary", "compensation", "HR rules").
  2. **Targeted Search**: Instead of relying on vector similarity alone, it uses precise
regex-based searching across the Company Wiki to locate exact policy matches.
  3. **Content Filtering**: It loads only the relevant pages, discarding hundreds of lines of
irrelevant documentation that would otherwise clutter the context window.
  4. **Knowledge Injection**: Finally, it summarizes critical policies, rules, and context (e.g.,
"Only HR Managers can view salaries") into a concise "Knowledge Block." This block
is injected directly into the Evaluator's system prompt, ensuring every decision is
made with full legal and procedural awareness.

### 2. The Evaluator ("The Brain")

- **Role**: High-Level Strategic Planner & Compliance Officer.
- **Engine**: nebius/openai/gpt-oss-120b (via LiteLLM).
- **Behavior**:
  - **Contextual Guardian**: The Evaluator serves as the gatekeeper. It continuously
monitors the who_ami endpoint to understand the current user's role (e.g., "Intern"
vs. "Executive") and cross-references this with the "Knowledge Block" provided by
the WikiAgent.
  - **Strict Guardrails**: It enforces a "Privacy First" doctrine. For example, if a public user
attempts to access internal employee IDs, the Evaluator intercepts this intent and
denies it immediately, preventing the Worker from ever touching the sensitive API
endpoints.
  - **Structured Reasoning**: It outputs a strict three-part thought process:
    - **THOUGHT**: A scratchpad for internal reasoning and policy checking.
    - **DECISION**: A binary flag (PROCEED or FINISH) to control the loop.
    - **INSTRUCTION**: A clear, natural-language directive for the Worker (e.g., "Search
for project 'Acme', get its ID, and then log 8 hours.").
  - **Crucial Distinction**: The Evaluator never writes code. Its sole responsibility is to
guide the Worker, ensuring a separation of concerns between high-level policy
adherence and low-level syntax execution.

### 3. The Worker ("The Hands")

- **Role**: Code Generation & Execution Engine.
- **Engine**: smolagents.CodeAgent.
- **Behavior**:
  - **Translation Layer**: The Worker receives high-level instructions from the Evaluator
and translates them into executable logic.
  - **Sandboxed Execution**: It generates valid Python code and executes it within a
secure sandbox environment. This allows for dynamic error handling and logic
branching that JSON agents cannot achieve.
  - **Logic Chaining**: A major advantage of this architecture is the ability to chain
operations. The Worker can perform a "Search -> Filter -> Update" sequence in a
single turn. For instance, it can search for a project, filter the results to find the active
one, extract the ID, and log time against it—all in one block of Python code.
  - **Statelessness**: The Worker is designed to be stateless. It relies entirely on the
Evaluator for context and instructions, ensuring that it never "hallucinates"
permissions or policies that were not explicitly provided.

## 🚀 Key Features & Design Philosophy

- **Model Upgrade (gpt-oss-120b)**:
  - The system is hardcoded to use the gpt-oss-120b model (approximate to the GPT-4
class).
  - **Why?** The baseline 20b model often struggles with complex instruction following and
nuanced code generation. The 120b model provides the necessary reasoning depth
to handle edge cases, such as ambiguous user requests or conflicting security
policies, and generates syntactically perfect Python code.
- **Code-First Execution via smolagents**:
  - Leveraging Hugging Face's smolagents, the system moves beyond the rigid "one tool
per turn" limit.
  - **Benefit**: This reduces the number of round-trips to the LLM. Instead of 3 separate
turns to find a user, get their ID, and update their profile, the Code Agent handles it in
one pass. It also allows for complex client-side filtering (e.g., "Find all projects where
the status is active AND the deadline is today").
- **Active RAG Implementation**:
  - Most agents dump the entire wiki into the context window, confusing the model with
irrelevant facts.
  - **Our Approach**: The WikiAgent actively filters knowledge first. If the task is about
"Time Tracking," the Evaluator will never see the "Kitchen Cleaning Protocols,"
keeping its attention focused solely on the relevant "Billing Rules."
- **Strict Privacy & Access Control**:
  - The Evaluator operates under a set of "Prime Directives" that explicitly forbid the
Worker from accessing sensitive data if is_public=True.
  - **Mechanism**: Before issuing any instruction, the Evaluator simulates the outcome
against the Wiki rules. If a violation is detected, it returns a denied_security response
without ever exposing the API to the risk of data leakage.

## 🛠 Setup & Installation Guide

Follow these steps to deploy the agent in your local environment.

### 1. Dependencies

Install the required Python packages. Note that smolagents is critical for the Code Agent
functionality.

```
pip install erc3 smolagents python-dotenv
```

### 2. Environment Variables

Create a .env file in the root directory of the project. This file securely stores your API keys.

```
# Benchmark Access: Your unique key for the ERC3 environment
ERC3_API_KEY=your_erc3_key_here

# Inference Provider: Points to the Nebius AI Studio for the 120b model
NEBIUS_API_BASE=https://api.studio.nebius.ai/v1/
NEBIUS_API_KEY=your_nebius_key_here
```

### 3. Running the Agent

Execute the main submission script to start the session. The script will automatically handle
authentication, task fetching, and result submission.

```
python submission.py
```

## ⚙ Configuration Details

The agent's behavior is customizable via constants defined in submission.py. Understanding
these settings helps in tuning performance.

| Setting | Value | Description |
|---------|-------|-------------|
| Model | gpt-oss-120b | The high-intelligence backbone. Changing this to a smaller model (e.g., 70b or 8b) will likely result in increased code generation errors and logic failures. |
| Max Turns | 7 | The hard limit on the number of Evaluator-Worker loops per task. This prevents infinite loops if the agent gets stuck. Most tasks complete in 2-4 turns. |
| Worker Steps | 2 | The maximum number of Python execution steps the Worker can take per instruction. This allows for a "try-catch-retry" pattern within a single turn. |
| Tooling | smolagents.tool | All 25+ ERC3 API endpoints are wrapped as Python tools with type hints and docstrings, serving as the "API Manual" for the model. |

## 🧰 Available Tools

The Worker agent has access to the full suite of ERC3 API endpoints, exposed as Python
functions.

### 👥 Employees & HR

- **list_employees(limit, offset)**: Paginated list of all employees.
- **search_employees(query, limit)**: Fuzzy search by name, skill, or role.
- **get_employee(id)**: Retrieve full profile (salary, skills, notes).
- **update_employee(employee_id, ...)**: Modify fields like salary or skills.

### 📁 Projects & Teams

- **list_projects(limit, offset)**: Paginated list of active/archived projects.
- **search_projects(query, team_member, ...)**: Find projects by name or team.
- **get_project(id)**: Get details, including team allocations.
- **update_project_team(project_id, team)**: Reallocate team members.
- **update_project_status(project_id, status)**: Change project lifecycle state.

### 🏢 Customers

- **list_customers(limit, offset)**: Paginated list of client companies.
- **search_customers(query, limit)**: Find customers by name.
- **get_customer(id)**: detailed view including deal phase and contacts.

### 📚 Knowledge Base (Wiki)

- **list_wiki()**: Get all available documentation paths.
- **search_wiki(query_regex)**: Regex search through wiki content.
- **load_wiki(file)**: Read the content of a specific markdown file.
- **update_wiki(file, content)**: Edit or create documentation.

### ⏱ Time Tracking

- **log_time(employee, project, hours, ...)**: Create new time entries.
- **get_time(id)**: Retrieve a specific entry.
- **update_time(id, ...)**: Modify hours, notes, or billable status.
- **search_time(employee, limit)**: Find entries for a specific person.
- **time_summary_by_project(...)**: Aggregate reports by project.
- **time_summary_by_employee(...)**: Aggregate reports by employee.

### 🔄 Context & Control

- **who_ami()**: Returns current user identity and permissions.
- **respond(message, outcome, links)**: Submit the final answer.
- **finish_task(reason)**: Terminate the agent loop.

## 🧩 Comprehensive Workflow Example

To illustrate the interplay between agents, consider the task: "Log 8 hours for Felix on the
Acme project."

1. **Phase 1: Knowledge Acquisition (WikiAgent)**
   - The WikiAgent analyzes the prompt and extracts keywords: "Time Logging", "Acme",
"Billable".
   - It regex-searches the Wiki and finds a relevant policy: "Contractors working on Acme
projects must mark work as non-billable."
   - It creates a Knowledge Block: {"Rule": "Acme projects = Non-billable for
contractors"} and injects it into the context.

2. **Phase 2: Strategic Planning (Evaluator)**
   - The Evaluator receives the task and the Knowledge Block.
   - It checks who_ami and sees the current user is "Felix" (a contractor).
   - Reasoning: "I need to find the project ID for Acme. I must also ensure the 'billable'
flag is set to False, per the Wiki rule."
   - Instruction: "Search for project 'Acme' to get its ID. Then, log 8 hours for
'felix_baum'. Crucially, set billable=False in accordance with company policy."

3. **Phase 3: Tactical Execution (Worker)**
   - The Worker receives the instruction.
   - It generates the following Python code:

```python
# Step 1: Find the project
projects = search_projects(query="Acme")
if projects:
    p_id = projects[0]['id']
    # Step 2: Log the time with the correct flags
    log_time(
        employee="felix_baum",
        project=p_id,
        hours=8.0,
        billable=False, # Explicitly following instruction
        notes="Work on Acme project"
    )
```

   - It executes the code in the sandbox. The API returns a success message.

4. **Phase 4: Completion (Evaluator)**
   - The Evaluator reviews the Worker's logs.
   - Seeing a successful API response, it instructs the Worker to call respond() with a
success message and then finish_task().

## 🛡 Response Outcomes & Error Handling Strategies

The system maps complex real-world situations to specific API outcomes to ensure
benchmark compliance.

- **ok_answer**:
  - **Usage**: The happy path. The task was completed successfully, or the requested
information was retrieved and presented.
- **denied_security**:
  - **Usage**: Used when a user requests sensitive data (Salaries, Deal Phases, Internal IDs)
or violates a specific Wiki rule.
  - **Example**: A public user asks, "What is the project ID for the secret launch?" ->
denied_security.
- **ok_not_found**:
  - **Usage**: Used when the agent has performed an exhaustive search (including
checking include_archived=True) and the entity genuinely does not exist.
  - **Nuance**: This is different from a search error; it implies the data is missing from the
world.
- **error_internal**:
  - **Usage**: A catch-all for Python exceptions, syntax errors in generated code, or 500
errors from the API. The Evaluator will usually try to retry once before settling on this
outcome.

## ⚠ Common Pitfalls / Troubleshooting

- **smolagents Missing**:
  - **Issue**: The script fails immediately with an import error.
  - **Fix**: Ensure you have installed the specific library version compatible with CodeAgent
using pip install smolagents.
- **Hallucinated IDs**:
  - **Issue**: The agent tries to get_project("proj_acme") without searching first.
  - **Fix**: The Evaluator system prompt explicitly forbids guessing. Ensure the prompt
emphasizes: "You must SEARCH before you GET."
- **Context Window Limits**:
  - **Issue**: Although gpt-oss-120b has a large context, injecting the entire wiki can still
cause "lost in the middle" retrieval errors.
  - **Fix**: Trust the WikiAgent to filter content. Do not manually force the loading of all wiki
pages.