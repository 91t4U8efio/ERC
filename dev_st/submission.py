import textwrap
import os
import sys
import time
import re
import json
import io
from contextlib import redirect_stdout
from typing import List, Dict, Any, Optional, Union

# --- Force Unbuffered Output ---
sys.stdout.reconfigure(line_buffering=True)

# --- Load Environment Variables ---
try:
    from dotenv import load_dotenv
    load_dotenv() 
except ImportError:
    pass

# --- Imports ---
try:
    from smolagents import CodeAgent, tool, LiteLLMModel
except ImportError:
    print("Error: smolagents not installed. Run: pip install smolagents")
    sys.exit(1)

try:
    from erc3 import ERC3, TaskInfo, ApiException
    from erc3 import erc3  # For accessing pydantic models (Req_*, EntityLink, etc.)
except ImportError:
    print("Error: erc3 not installed. Run: pip install erc3")
    sys.exit(1)

# ==============================================================================
# LOGGING SYSTEM
# ==============================================================================
class ActionLogger:
    """
    Captures tool interactions to:
    1. Print them to stdout (for the user) in the requested format.
    2. Buffer them for the Evaluator.
    """
    def __init__(self):
        self._logs = []

    def log(self, message: str):
        print(message, flush=True)
        self._logs.append(message)

    def log_error(self, message: str):
        self._logs.append(message)

    def get_history_entry(self) -> str:
        if not self._logs:
            return "No API interactions recorded this turn."
        return "\n".join(self._logs)

    def clear(self):
        self._logs = []

# ==============================================================================
# SHARED KNOWLEDGE BASE
# ==============================================================================
BENCHMARK_CONTEXT = """
### 1. ENVIRONMENT & DATA STRUCTURES
You are a business assistant for a company. You must adhere to strict access control and privacy rules specific to the current company context.

**A. Access Control**
- **Executives**: Broad access to all data.
- **Project Leads**: Can modify projects they lead.
- **Team Members**: Read access to most data.
- **Guests/Public (is_public=true)**: PUBLIC DATA ONLY. No internal details (salaries, deal phases, employee IDs).

**B. Key Entities**
- **Employee**: `id`, `name`, `email`, `salary` (SENSITIVE), `location`, `department`, `skills`, `wills`, `notes`.
- **Project**: `id`, `name`, `customer`, `status`, `description`, `team` (list of allocations with employee, time_slice, role).
- **Customer**: `id`, `name`, `brief`, `location`, `deal_phase` (SENSITIVE), `high_level_status`, `account_manager`, `primary_contact_name`, `primary_contact_email`.
- **TimeEntry**: `id`, `employee`, `customer`, `project`, `date`, `hours`, `work_category`, `notes`, `billable`, `status`.
- **Wiki**: `path`, `content`.

### 2. AVAILABLE TOOLS

**Context Tools:**
- `who_ami()` → Dict: Returns current user context (current_user, is_public, location, department, today, wiki_sha1).

**Employee Tools:**
- `list_employees(limit=5, offset=0)` → Dict: List employees with pagination.
- `search_employees(query, limit=5)` → List[Dict]: Search employees by text.
- `get_employee(id)` → Dict: Get full employee profile by ID.
- `update_employee(employee_id, salary, skills, wills, notes)` → Dict: Update employee info.

**Project Tools:**
- `list_projects(limit=5, offset=0)` → Dict: List projects with pagination.
- `search_projects(query, limit=5)` → List[Dict]: Search projects by text.
- `get_project(id)` → Dict: Get detailed project info including team.
- `update_project_team(project_id, team)` → str: Update project team allocation.
- `update_project_status(project_id, status)` → str: Update project status.

**Customer Tools:**
- `list_customers(limit=5, offset=0)` → Dict: List customers with pagination.
- `search_customers(query, limit=5)` → List[Dict]: Search customers by text.
- `get_customer(id)` → Dict: Get full customer record.

**Wiki Tools:**
- `list_wiki()` → Dict: List all wiki article paths.
- `search_wiki(query_regex)` → List[Dict]: Search wiki articles using regex.
- `load_wiki(file)` → Dict: Load wiki article content.
- `update_wiki(file, content)` → str: Create or update wiki page.

**Time Tracking Tools:**
- `log_time(employee, project, hours, date, notes, billable=True)` → Dict: Log a new time entry.
- `get_time(id)` → Dict: Get a time entry by ID.
- `update_time(id, date, hours, notes, billable, status)` → str: Update an existing time entry.
- `search_time(employee, limit=10)` → List[Dict]: Search time entries for an employee.
- `time_summary_by_project(date_from, date_to, projects)` → List[Dict]: Get time summary grouped by project.
- `time_summary_by_employee(date_from, date_to, employees)` → List[Dict]: Get time summary grouped by employee.

**Response Tools:**
- `respond(message, outcome, links)` → str: **FINAL ACTION**. Submit the answer to the user.
  - `outcome`: MUST be one of: 'ok_answer', 'ok_not_found', 'denied_security', 'none_clarification_needed', 'none_unsupported', 'error_internal'.
  - `links`: List of entity references, e.g., [{"kind": "employee", "id": "john_doe"}, {"kind": "project", "id": "proj_123"}].
- `finish_task(reason)` → str: Signal task completion. Call AFTER respond().

### 3. CRITICAL RULES
- **Context Awareness**: Always check `who_ami()` first to determine user role and visibility scope.
- **Privacy**: NEVER reveal sensitive data (salary, deal_phase) to unauthorized users (is_public=true or non-privileged).
- **Entity Linking**: When responding, ALWAYS provide `links` to referenced entities (employees, projects, customers, wiki).
- **Pagination Limits**: All search/list tools have a maximum limit of 5 results per call.
- **Valid Outcomes**: Use correct outcome values - 'ok_answer' for success, 'denied_security' for privacy violations, 'ok_not_found' if no data found.
"""

# ==============================================================================
# TOOL FACTORY
# ==============================================================================
def create_tools(client, logger: ActionLogger):
    
    task_state = {"completed": False}

    def dispatch_and_log(req, endpoint_path: str):
        req_data = req.model_dump()
        log_payload = {"tool": endpoint_path, **req_data}
        logger.log(f"    [REQ ->] {json.dumps(log_payload)}")

        try:
            resp = client.dispatch(req)
        except Exception as e:
            logger.log(f"    [<- RESP ERROR] {str(e)}")
            raise e

        if hasattr(resp, 'model_dump'):
            resp_data = resp.model_dump()
            logger.log(f"    [<- RESP] {json.dumps(resp_data)}")
        else:
            logger.log(f"    [<- RESP] Success")
            
        return resp

    # --- Context Tools ---
    @tool
    def who_ami() -> Dict[str, Any]:
        """Returns the current user context and visibility scope."""
        try:
            req = erc3.Req_WhoAmI()
            resp = dispatch_and_log(req, "/whoami")
            return resp.model_dump()
        except ApiException as e:
            return {"error": str(e)}

    # --- Employee Tools ---
    @tool
    def list_employees(limit: int = 5, offset: int = 0) -> Dict[str, Any]:
        """
        List employees with pagination.

        Args:
            limit: Maximum number of employees to return (max 5).
            offset: Number of employees to skip.
        """
        try:
            req = erc3.Req_ListEmployees(limit=limit, offset=offset)
            resp = dispatch_and_log(req, "/employees/list")
            return {
                "next_offset": resp.next_offset,
                "employees": [e.model_dump() for e in resp.employees] if resp.employees else []
            }
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def search_employees(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search employees by text.

        Args:
            query: The search query string.
            limit: Maximum number of results to return (max 5).
        """
        try:
            req = erc3.Req_SearchEmployees(query=query, limit=limit, offset=0)
            resp = dispatch_and_log(req, "/employees/search")
            return [e.model_dump() for e in resp.employees] if resp.employees else []
        except ApiException as e:
            return [{"error": str(e)}]

    @tool
    def get_employee(id: str) -> Dict[str, Any]:
        """
        Get full employee profile by ID.

        Args:
            id: The ID of the employee to retrieve.
        """
        try:
            req = erc3.Req_GetEmployee(id=id)
            resp = dispatch_and_log(req, "/employees/get")
            return resp.employee.model_dump() if resp.employee else {}
        except ApiException as e:
            return {"error": str(e)}

    # --- Project Tools ---
    @tool
    def list_projects(limit: int = 5, offset: int = 0) -> Dict[str, Any]:
        """
        List projects with pagination.

        Args:
            limit: Maximum number of projects to return (max 5).
            offset: Number of projects to skip.
        """
        try:
            req = erc3.Req_ListProjects(limit=limit, offset=offset)
            resp = dispatch_and_log(req, "/projects/list")
            return {
                "next_offset": resp.next_offset,
                "projects": [p.model_dump() for p in resp.projects] if resp.projects else []
            }
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def search_projects(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search projects by text.

        Args:
            query: The search query string.
            limit: Maximum number of results to return (max 5).
        """
        try:
            req = erc3.Req_SearchProjects(query=query, limit=limit, offset=0)
            resp = dispatch_and_log(req, "/projects/search")
            return [p.model_dump() for p in resp.projects] if resp.projects else []
        except ApiException as e:
            return [{"error": str(e)}]

    @tool
    def get_project(id: str) -> Dict[str, Any]:
        """
        Get detailed project info.

        Args:
            id: The ID of the project to retrieve.
        """
        try:
            req = erc3.Req_GetProject(id=id)
            resp = dispatch_and_log(req, "/projects/get")
            return resp.project.model_dump() if resp.project else {}
        except ApiException as e:
            return {"error": str(e)}

    # --- Customer Tools ---
    @tool
    def list_customers(limit: int = 5, offset: int = 0) -> Dict[str, Any]:
        """
        List customers with pagination.

        Args:
            limit: Maximum number of customers to return (max 5).
            offset: Number of customers to skip.
        """
        try:
            req = erc3.Req_ListCustomers(limit=limit, offset=offset)
            resp = dispatch_and_log(req, "/customers/list")
            return {
                "next_offset": resp.next_offset,
                "companies": [c.model_dump() for c in resp.companies] if resp.companies else []
            }
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def search_customers(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search customers by text.

        Args:
            query: The search query string.
            limit: Maximum number of results to return (max 5).
        """
        try:
            req = erc3.Req_SearchCustomers(query=query, limit=limit, offset=0)
            resp = dispatch_and_log(req, "/customers/search")
            return [c.model_dump() for c in resp.companies] if resp.companies else []
        except ApiException as e:
            return [{"error": str(e)}]

    @tool
    def get_customer(id: str) -> Dict[str, Any]:
        """
        Get full customer record.

        Args:
            id: The ID of the customer to retrieve.
        """
        try:
            req = erc3.Req_GetCustomer(id=id)
            resp = dispatch_and_log(req, "/customers/get")
            return resp.company.model_dump() if resp.company else {}
        except ApiException as e:
            return {"error": str(e)}

    # --- Wiki Tools ---
    @tool
    def list_wiki() -> Dict[str, Any]:
        """List all wiki article paths."""
        try:
            req = erc3.Req_ListWikiPages()
            resp = dispatch_and_log(req, "/wiki/list")
            return resp.model_dump()
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def search_wiki(query_regex: str) -> List[Dict[str, Any]]:
        """
        Search wiki articles using regex.

        Args:
            query_regex: The regex pattern to search for in wiki pages.
        """
        try:
            req = erc3.Req_SearchWikiPages(query_regex=query_regex)
            resp = dispatch_and_log(req, "/wiki/search")
            return [r.model_dump() for r in resp.results] if resp.results else []
        except ApiException as e:
            return [{"error": str(e)}]

    @tool
    def load_wiki(file: str) -> Dict[str, Any]:
        """
        Load wiki article content.

        Args:
            file: The path of the wiki file to load.
        """
        try:
            req = erc3.Req_LoadWikiPage(file=file)
            resp = dispatch_and_log(req, "/wiki/load")
            return resp.model_dump()
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def update_wiki(file: str, content: str) -> str:
        """
        Create or update a wiki page.

        Args:
            file: The path of the wiki file to update.
            content: The new content for the wiki page.
        """
        try:
            req = erc3.Req_UpdateWikiPage(file=file, content=content, changed_by="")
            dispatch_and_log(req, "/wiki/update")
            return "Wiki page updated successfully."
        except ApiException as e:
            return f"Error updating wiki: {e}"

    # --- Time Tools ---
    @tool
    def log_time(employee: str, project: str, hours: float, date: str, notes: str, billable: bool = True) -> Dict[str, Any]:
        """
        Log a new time entry.

        Args:
            employee: The ID of the employee.
            project: The ID of the project.
            hours: Number of hours worked.
            date: Date of work (YYYY-MM-DD).
            notes: Description of work done.
            billable: Whether the work is billable.
        """
        try:
            req = erc3.Req_LogTimeEntry(
                employee=employee, project=project, hours=hours, date=date, 
                notes=notes, billable=billable, work_category="customer_project" # Defaulting for simplicity
            )
            resp = dispatch_and_log(req, "/time/log")
            return resp.model_dump()
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def get_time(id: str) -> Dict[str, Any]:
        """
        Get a time entry by ID.

        Args:
            id: The ID of the time entry.
        """
        try:
            req = erc3.Req_GetTimeEntry(id=id)
            resp = dispatch_and_log(req, "/time/get")
            return resp.entry.model_dump() if resp.entry else {}
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def update_time(id: str, date: str, hours: float, notes: str, billable: bool, status: str) -> str:
        """
        Update an existing time entry.

        Args:
            id: The ID of the time entry to update.
            date: New date (YYYY-MM-DD).
            hours: New number of hours.
            notes: New notes.
            billable: New billable status.
            status: New status (e.g., 'draft', 'submitted').
        """
        try:
            req = erc3.Req_UpdateTimeEntry(
                id=id, date=date, hours=hours, notes=notes, 
                billable=billable, status=status, work_category="customer_project", changed_by=""
            )
            dispatch_and_log(req, "/time/update")
            return "Time entry updated successfully."
        except ApiException as e:
            return f"Error updating time entry: {e}"

    @tool
    def search_time(employee: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search time entries for an employee.

        Args:
            employee: The ID of the employee.
            limit: Maximum number of entries to return (max 5).
        """
        try:
            req = erc3.Req_SearchTimeEntries(employee=employee, limit=limit, offset=0)
            resp = dispatch_and_log(req, "/time/search")
            return [e.model_dump() for e in resp.entries] if resp.entries else []
        except ApiException as e:
            return [{"error": str(e)}]

    @tool
    def time_summary_by_project(date_from: str, date_to: str, projects: List[str]) -> List[Dict[str, Any]]:
        """
        Get time summary grouped by project.

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).
            projects: List of project IDs to summarize.
        """
        try:
            req = erc3.Req_TimeSummaryByProject(date_from=date_from, date_to=date_to, projects=projects)
            resp = dispatch_and_log(req, "/time/summary/by-project")
            return [s.model_dump() for s in resp.summaries] if resp.summaries else []
        except ApiException as e:
            return [{"error": str(e)}]

    @tool
    def time_summary_by_employee(date_from: str, date_to: str, employees: List[str]) -> List[Dict[str, Any]]:
        """
        Get time summary grouped by employee.

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).
            employees: List of employee IDs to summarize.
        """
        try:
            req = erc3.Req_TimeSummaryByEmployee(date_from=date_from, date_to=date_to, employees=employees)
            resp = dispatch_and_log(req, "/time/summary/by-employee")
            return [s.model_dump() for s in resp.summaries] if resp.summaries else []
        except ApiException as e:
            return [{"error": str(e)}]

    # --- Update Tools ---
    @tool
    def update_employee(employee_id: str, salary: int, skills: List[Dict[str, Any]], wills: List[Dict[str, Any]], notes: str) -> Dict[str, Any]:
        """
        Update employee info (salary, skills, wills, notes).

        Args:
            employee_id: The ID of the employee.
            salary: New salary amount.
            skills: List of skill objects.
            wills: List of will objects.
            notes: New notes.
        """
        try:
            # Construct proper objects
            skill_objs = [erc3.Skill(**s) for s in skills]
            will_objs = [erc3.Will(**w) for w in wills]
            
            req = erc3.Req_UpdateEmployeeInfo(
                employee=employee_id, salary=salary, skills=skill_objs, wills=will_objs, notes=notes, changed_by=""
            )
            resp = dispatch_and_log(req, "/employees/update")
            return resp.employee.model_dump() if resp.employee else {}
        except ApiException as e:
            return {"error": str(e)}

    @tool
    def update_project_team(project_id: str, team: List[Dict[str, Any]]) -> str:
        """
        Update project team allocation.

        Args:
            project_id: The ID of the project.
            team: List of team member objects.
        """
        try:
            team_objs = [erc3.ProjectMember(**m) for m in team]
            req = erc3.Req_UpdateProjectTeam(id=project_id, team=team_objs, changed_by="")
            dispatch_and_log(req, "/projects/team/update")
            return "Project team updated successfully."
        except ApiException as e:
            return f"Error updating project team: {e}"

    @tool
    def update_project_status(project_id: str, status: str) -> str:
        """
        Update project status.

        Args:
            project_id: The ID of the project.
            status: New status string.
        """
        try:
            req = erc3.Req_UpdateProjectStatus(id=project_id, status=status, changed_by="")
            dispatch_and_log(req, "/projects/status/update")
            return "Project status updated successfully."
        except ApiException as e:
            return f"Error updating project status: {e}"

    # --- Final Response Tool ---
    @tool
    def respond(message: str, outcome: str = "ok_answer", links: List[Dict[str, str]] = []) -> str:
        """
        Submits the final response for the task.
        Args:
            message: The text response to the user.
            outcome: One of 'ok_answer', 'ok_not_found', 'denied_security', 'none_clarification_needed', 'none_unsupported', 'error_internal'.
            links: List of entities referenced, e.g., [{"kind": "employee", "id": "..."}]
        """
        if task_state["completed"]: return "Task already completed."
        
        # Convert dict links to proper objects if needed, but the API expects specific structure
        # The tool receives basic types. We need to construct the request.
        
        # Helper to parse links if passed as json string or list of dicts
        parsed_links = []
        for l in links:
            if isinstance(l, dict):
                parsed_links.append(erc3.AgentLink(kind=l.get("kind"), id=l.get("id")))
        
        try:
            req = erc3.Req_ProvideAgentResponse(message=message, outcome=outcome, links=parsed_links)
            dispatch_and_log(req, "/respond")
            task_state["completed"] = True
            return "Response Submitted Successfully. Task Finished."
        except ApiException as e:
            return f"Error submitting response: {e}"

    @tool
    def finish_task(reason: str) -> str:
        """
        Signals that the task is complete. Call this AFTER calling respond() to end the task loop.
        
        Args:
            reason: Brief explanation of why the task is finished (e.g., 'Response submitted', 'Cannot complete - no data found').
        """
        task_state["completed"] = True
        logger.log(f"[TASK FINISHED] {reason}")
        return f"Task marked as finished: {reason}"

    return [
        who_ami, 
        list_employees, search_employees, get_employee, update_employee,
        list_projects, search_projects, get_project, update_project_team, update_project_status,
        list_customers, search_customers, get_customer,
        list_wiki, search_wiki, load_wiki, update_wiki,
        log_time, get_time, update_time, search_time, time_summary_by_project, time_summary_by_employee,
        respond, finish_task
    ]

# ==============================================================================
# AGENT 1: THE EVALUATOR (PLANNER)
# ==============================================================================
class EvaluatorAgent:
    def __init__(self, model_id: str, task_description: str):
        self.model = LiteLLMModel(
            model_id=model_id,
            api_base=os.getenv("NEBIUS_API_BASE"),
            api_key=os.getenv("NEBIUS_API_KEY")
        )
        self.task_description = task_description
        
        self.system_prompt = textwrap.dedent(f"""
            You are the **Evaluator Agent** (The Brain) for an AI Business Assistant.
            You direct a **Worker Agent** (The Hands) who executes Python code.
            
            {BENCHMARK_CONTEXT}
            
            <PRIME_DIRECTIVES>
            1. **NO CODING**: DO NOT WRITE CODE. Define the *Plan*.
            2. **STATE AWARENESS**: Worker is stateless. Provide all IDs/Context in INSTRUCTION.
            3. **PRIVACY FIRST**: Check `who_ami` output. If public, DO NOT access/reveal internal data.
            4. **CONTEXT MONITORING**: Watch `wiki_sha1` in `who_ami`. If it changes, the company context (rules/entities) might have changed.
            5. **ENTITY LINKING**: Collect IDs of all relevant entities (Projects, Customers, People) for the final `respond` call.
            6. **FINALIZATION**: Use `respond()` to finish. Provide a clear message and ALL relevant links.
            </PRIME_DIRECTIVES>

            <OUTPUT_FORMAT>
            THOUGHT: [Reasoning based on logs and context]
            DECISION: [PROCEED | FINISH]
            INSTRUCTION: [Specific goal for the Worker in natural language or Python code. DO NOT OUTPUT JSON.]
            </OUTPUT_FORMAT>
        """)

    def decide_next_step(self, history: List[str], user_context: Dict[str, Any], last_decision: Optional[str] = None) -> str:
        context_str = "\n".join(history[-4:])
        previous_context = f"YOUR PREVIOUS DECISION:\n{last_decision}\n\n" if last_decision else ""

        prompt = (
            f"{self.system_prompt}\n\n"
            f"MAIN TASK: {self.task_description}\n\n"
            f"CURRENT USER CONTEXT:\n{json.dumps(user_context, indent=2)}\n\n"
            f"{previous_context}"
            f"EXECUTION LOGS (Last 2 Steps):\n{context_str}\n\n"
            "Determine the next step."
        )
        
        print(f"\n[Evaluator] Thinking...", flush=True)
        try:
            response = self.model(messages=[{"role": "user", "content": prompt}])
            content = response.content
            print(f"\n[Evaluator] Decision:\n{content}", flush=True)
            return content
        except Exception as e:
            print(f"[Evaluator] Error: {e}", flush=True)
            raise e

# ==============================================================================
# AGENT 2: THE WORKER (CODE AGENT)
# ==============================================================================
def create_worker_agent(model_id: str, tools: list):
    model = LiteLLMModel(
            model_id=model_id,
            api_base=os.getenv("NEBIUS_API_BASE"),
            api_key=os.getenv("NEBIUS_API_KEY")
            )
    
    agent = CodeAgent(
        tools=tools,
        model=model,
        add_base_tools=True,
        additional_authorized_imports=["math", "json", "time", "re", "datetime"],
        max_steps=2, 
        verbosity_level=0
    )
    return agent

# ==============================================================================
# COORDINATOR LOOP
# ==============================================================================
def run_coordinator(model_id: str, api: ERC3, task: TaskInfo):
    dev_client = api.get_erc_dev_client(task)
    
    logger = ActionLogger()
    tools_list = create_tools(dev_client, logger)
    
    evaluator = EvaluatorAgent(model_id, task.task_text)
    
    history = []
    last_decision = None
    
    print(f"\n>>> COORDINATOR STARTING TASK: {task.task_text}", flush=True)
    
    # Initial Context Fetch
    user_context = {}
    try:
        who = dev_client.who_am_i()
        user_context = who.model_dump()
        print(f"[Coordinator] User Context: {user_context.get('current_user', 'PUBLIC')}", flush=True)
    except Exception as e:
        print(f"[Coordinator] Failed to fetch context: {e}")

    max_turns = 7 
    for turn in range(max_turns):
        print(f"\n--- TURN {turn + 1} ---", flush=True)
        logger.clear()
        
        # Evaluator Step
        decision_text = evaluator.decide_next_step(history, user_context, last_decision)
        last_decision = decision_text
        
        # Parse Decision
        instruction = ""
        if "INSTRUCTION:" in decision_text:
            instruction = decision_text.split("INSTRUCTION:", 1)[1].strip()
        else:
            instruction = decision_text.split('\n')[-1].strip()

        if "DECISION: FINISH" in decision_text and "respond" not in instruction.lower():
             # If evaluator thinks it's done but didn't instruct to respond, we might be in a weird state.
             # But usually the instruction will contain the final action.
             pass

        print(f"\n[Coordinator] GOAL: {instruction}", flush=True)
        
        worker_prompt = (
            f"""{BENCHMARK_CONTEXT}
            
            ROLE:
            Your job is to write code according to GOAL instruction. 
            You should do that defined in the GOAL exactly based on the store environment rules above.

            GOAL: {instruction}
            
            PYTHON CODING RULES (STRICT):
            1. Output valid Python code in a markdown block: ```python ... ```
            2. **NO BARE RAISE**: Do not use `raise` without arguments. Use `raise Exception("Context description")`.
            3. **DEFENSIVE CODING**: When filtering lists, check if the list is empty before accessing index `[0]`.
            4. Use `print()` to log details for the Evaluator.
            5. Use `final_answer('DONE')` to signal completion.
            6. IMPORTANT: Perform ONLY the steps requested in the GOAL. Do NOT assume previous variables exist.
            7. **FINAL RESPONSE**: If the goal is to answer the user, use the `respond` tool.
            8. **LINKS**: When using `respond`, construct the `links` list carefully: `[{{"kind": "employee", "id": "..."}}, ...]`.
            9. **COMPLETION**: After calling `respond`, call `finish_task(reason)` to end the task.
            """
        )
        
        try:
            worker = create_worker_agent(model_id, tools_list)
            
            captured_io = io.StringIO()
            with redirect_stdout(captured_io):
                worker.run(worker_prompt)
            
            worker_output = captured_io.getvalue()
            print(worker_output, flush=True)
            
            # Check for completion signal in logs
            if "[TASK FINISHED]" in worker_output or ("/respond" in worker_output and "Task Finished" in worker_output):
                print(">>> Task Completed.")
                return "Success"

            history.append(f"Evaluator Instruction: {instruction}")
            history.append(f"Worker Execution Logs:\n{worker_output}")
            
        except Exception as e:
            error_msg = f"Worker Error: {e}"
            print(error_msg, flush=True)
            history.append(f"Evaluator Instruction: {instruction}")
            history.append(f"Worker Error: {error_msg}")

    return "Max turns reached"

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    MODEL_ID = "nebius/openai/gpt-oss-20b"
    
    if "ERC3_API_KEY" not in os.environ:
        print("ERROR: 'ERC3_API_KEY' is missing. Check your .env file.")
        # sys.exit(1)

    print("Initializing ERC3 Session (Dev Agent - Dual Architecture)...", flush=True)
    try:
        core = ERC3()
        res = core.start_session(
            benchmark="erc3-dev",
            workspace="my",
            name="dev_agent_dual_v1",
            architecture="Evaluator-Worker Dual Agent"
        )
    except Exception as e:
        print(f"Failed to start session: {e}")
        return

    status = core.session_status(res.session_id)
    print(f"Session ID: {res.session_id}", flush=True)

    for i, task in enumerate(status.tasks):
        print(f"\n{'='*60}")
        print(f"TASK {i+1}/{len(status.tasks)} | ID: {task.task_id}")
        print(f"{'='*60}", flush=True)

        core.start_task(task)
        
        try:
            run_coordinator(MODEL_ID, core, task)
        except Exception as e:
            print(f"Task Failed: {e}", flush=True)

        result = core.complete_task(task)
        
        if result.eval:
            score_color = "\033[92m" if result.eval.score == 1.0 else "\033[91m"
            reset = "\033[0m"
            explain = ""
            if result.eval.logs:
                explain = "\n" + result.eval.logs
            print(f"\nSCORE: {score_color}{result.eval.score}{reset}{explain}")
        else:
            print("\nTask completed (No evaluation info).", flush=True)

    core.submit_session(res.session_id)
    print("Session Submitted.", flush=True)

if __name__ == "__main__":
    main()
