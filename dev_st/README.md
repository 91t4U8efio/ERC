# ERC3 Dev Agent - Dual Architecture

This agent is designed for the **ERC3-DEV** and **ERC3-TEST** benchmarks using a **Dual Agent Architecture** (Evaluator + Worker).

## Architecture

The agent uses a two-tier approach:

- **Evaluator Agent (The Brain)**: High-level planner that analyzes the task, user context, and execution logs to determine the next step. Uses `LiteLLMModel` for reasoning.
- **Worker Agent (The Hands)**: Executes Python code to interact with the ERC3 API using 27 available tools. Uses `smolagents.CodeAgent` with `max_steps=2`.
- **Coordinator Loop**: Manages the interaction between Evaluator and Worker, with a maximum of 7 turns per task.

## Key Features

- **27 Tools**: Complete coverage of all ERC3 API endpoints (employees, projects, customers, wiki, time tracking)
- **Access Control**: Strict privacy enforcement based on user role (`is_public`, department, etc.)
- **Entity Linking**: Automatic collection and linking of referenced entities in responses
- **Task Completion**: `finish_task()` tool signals completion and breaks the coordinator loop
- **Context Awareness**: Monitors `wiki_sha1` for company context changes

## Tools Available

**Context**: `who_ami`  
**Employees**: `list_employees`, `search_employees`, `get_employee`, `update_employee`  
**Projects**: `list_projects`, `search_projects`, `get_project`, `update_project_team`, `update_project_status`  
**Customers**: `list_customers`, `search_customers`, `get_customer`  
**Wiki**: `list_wiki`, `search_wiki`, `load_wiki`, `update_wiki`  
**Time**: `log_time`, `get_time`, `update_time`, `search_time`, `time_summary_by_project`, `time_summary_by_employee`  
**Response**: `respond`, `finish_task`

## Setup

1. Install dependencies:
   ```bash
   pip install erc3 smolagents python-dotenv
   ```

2. Set environment variables (create `.env` file):
   ```
   ERC3_API_KEY=your_api_key
   NEBIUS_API_BASE=https://api.studio.nebius.ai/v1/
   NEBIUS_API_KEY=your_nebius_key
   ```

3. Run the agent:
   ```bash
   python submission.py
   ```

## Configuration

- **Model**: `nebius/openai/gpt-oss-20b` (configurable in `main()`)
- **Max Turns**: 7 per task
- **Worker Max Steps**: 2 per turn
- **Pagination Limit**: 5 results max for all search/list operations

## How It Works

1. **Initialization**: Coordinator fetches user context via `who_ami()`
2. **Evaluation**: Evaluator analyzes task and context, outputs `THOUGHT`, `DECISION`, and `INSTRUCTION`
3. **Execution**: Worker receives instruction, generates Python code, executes tools
4. **Logging**: All API interactions are logged and fed back to Evaluator
5. **Iteration**: Loop continues until `respond()` + `finish_task()` called or max turns reached
6. **Completion**: Task marked complete, moves to next task

## Privacy & Access Control

The agent enforces strict access rules:
- **Public users** (`is_public=true`): No access to salaries, deal phases, or internal employee IDs
- **Team members**: Read-only access to most data
- **Project leads**: Can modify their own projects
- **Executives**: Broad access to all data

## Valid Response Outcomes

When calling `respond()`, use one of these outcomes:
- `ok_answer` - Successfully answered the request
- `ok_not_found` - No data found for the query
- `denied_security` - Privacy/security violation
- `none_clarification_needed` - Need more info from user
- `none_unsupported` - Request not supported
- `error_internal` - Internal error occurred
