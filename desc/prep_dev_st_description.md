# ERC3 Benchmark: Aetherion Analytics

## Environment Description

**Aetherion Analytics Gmb** is the setting for the Enterprise RAG Challenge 3 (ERC3). You are building an AI Agent acting as a business assistant to help employees and customers of Aetherion.

### Key Concepts

- **Role**: Your agent acts as a knowledgeable assistant. It must respect the current user's access permissions.
- **Access Control**:
    - **Executives**: Broad access to all data.
    - **Project Leads**: Can modify projects they lead.
    - **Team Members**: Read access to most data.
    - **Guests/Public**: Strictly public-safe data only. No internal details (salaries, deal phases, etc.).
- **Entities**:
    - **Employees**: Internal staff with skills, "wills" (interests), and roles.
    - **Customers**: External clients with deal statuses.
    - **Projects**: Engagements with customers, involving a team of employees.
    - **Time Entries**: Logs of work done, billable or non-billable.
    - **Wiki**: Internal documentation and culture notes.

### Benchmark Specifics (ERC3-DEV & ERC3-TEST)

- **Multi-Tenancy**: The final benchmark will feature 3-4 different companies. Aetherion is just one scenario.
    - **Context Awareness**: Agents must monitor `wiki_sha1` in `/whoami` to detect context changes (e.g., acquisitions or switching to a different company tenant).
- **Latency**: API calls have a simulated delay of **~300ms** to mimic real-world conditions.
- **Scoring**: The baseline agent scores ~56.2 on ERC3-DEV.

### External Resources

- **Platform**: [erc.timetoact-group.at](https://erc.timetoact-group.at/)
- **Registration**: [Event Registration](https://www.timetoact-group.at/events/enterprise-rag-challenge-part-3)
- **Agent Examples**: [GitHub: trustbit/erc3-agents](https://github.com/trustbit/erc3-agents)
- **Release Notes**: [Release Notes](https://erc.timetoact-group.at/releases)
- **Video Overview**: [YouTube (Russian)](https://www.youtube.com/watch?v=3Ndotm_e4OM)

## API Reference

The benchmark provides a set of HTTP endpoints to interact with the environment.

### 1. Context & Response

#### `POST /whoami`
Resolve the current user and visibility scope.

**Request**: `{}`
**Response**:
```json
{
  "current_user": "helene_stutz",
  "is_public": false,
  "location": "Amsterdam",
  "department": "Consulting",
  "today": "",
  "wiki_sha1": ""
}
```

#### `POST /respond`
Submit an agent-formatted reply with references.

**Request**:
```json
{
  "message": "I can help with lead coverage for Nordic accounts.",
  "outcome": "ok_answer",
  "links": [
    {
      "kind": "project",
      "id": "proj_nordiclogistics_route_scenario_lab"
    },
    {
      "kind": "customer",
      "id": "cust_nordic_logistics_group"
    },
    {
      "kind": "employee",
      "id": "helene_stutz"
    }
  ]
}
```
**Response**: `{}`

### 2. Employees

#### `POST /employees/list`
List employees with pagination.

**Request**:
```json
{
  "offset": 0,
  "limit": 5
}
```
**Response**:
```json
{
  "next_offset": 5,
  "employees": [
    {
      "id": "elena_vogel",
      "name": "Elena Vogel",
      "email": "elena_vogel@aetherion.com",
      "salary": 140000,
      "location": "Munich",
      "department": "Executive Leadership"
    },
    {
      "id": "marko_petrovic",
      "name": "Marko Petrovic",
      "email": "marko_petrovic@aetherion.com",
      "salary": 135000,
      "location": "Munich",
      "department": "Executive Leadership"
    }
  ]
}
```

#### `POST /employees/search`
Search employees by text, location, or skills.

**Request**:
```json
{
  "query": "edge deployment",
  "limit": 3,
  "offset": 0,
  "location": "Vienna",
  "department": "AI Engineering",
  "manager": "",
  "skills": [
    {
      "name": "edge_ai",
      "min_level": 4,
      "max_level": 0
    }
  ],
  "wills": [
    {
      "name": "knowledge_sharing",
      "min_level": 4,
      "max_level": 0
    }
  ]
}
```
**Response**:
```json
{
  "next_offset": 3,
  "employees": [
    {
      "id": "lukas_brenner",
      "name": "Lukas Brenner",
      "email": "lukas_brenner@aetherion.com",
      "salary": 115000,
      "location": "Vienna",
      "department": "AI Engineering"
    },
    {
      "id": "felix_baum",
      "name": "Felix Baum",
      "email": "felix_baum@aetherion.com",
      "salary": 98000,
      "location": "Munich",
      "department": "AI Engineering"
    }
  ]
}
```

#### `POST /employees/get`
Get full employee profile by ID.

**Request**:
```json
{
  "id": "elena_vogel"
}
```
**Response**:
```json
{
  "employee": {
    "id": "elena_vogel",
    "name": "Elena Vogel",
    "email": "elena_vogel@aetherion.com",
    "salary": 140000,
    "notes": "CEO and co-founder; focuses on customer relationships and making AI tangible, not just slides.",
    "location": "Munich",
    "department": "Executive Leadership",
    "skills": [
      {
        "name": "clarity_of_thought",
        "level": 5
      },
      {
        "name": "narrative_building",
        "level": 5
      },
      {
        "name": "risk_awareness",
        "level": 4
      },
      {
        "name": "stakeholder_alignment",
        "level": 5
      },
      {
        "name": "workshop_facilitation",
        "level": 4
      }
    ],
    "wills": [
      {
        "name": "cross_functional_collab",
        "level": 5
      },
      {
        "name": "ethical_judgment",
        "level": 4
      },
      {
        "name": "experimentation_mindset",
        "level": 4
      },
      {
        "name": "knowledge_sharing",
        "level": 5
      }
    ]
  }
}
```

#### `POST /employees/update`
Update salary, skills, notes, and assignment.

**Request**:
```json
{
  "employee": "felix_baum",
  "notes": "Supporting edge rollout for Acme's plant.",
  "salary": 99000,
  "skills": [
    {
      "name": "edge_ai",
      "level": 4
    },
    {
      "name": "ml_engineering",
      "level": 4
    }
  ],
  "wills": [
    {
      "name": "experimentation_mindset",
      "level": 5
    },
    {
      "name": "knowledge_sharing",
      "level": 4
    }
  ],
  "location": "Munich",
  "department": "AI Engineering",
  "changed_by": ""
}
```
**Response**:
```json
{
  "employee": {
    "id": "felix_baum",
    "name": "Felix Baum",
    "email": "felix_baum@aetherion.com",
    "salary": 99000,
    "notes": "Supporting edge rollout for Acme's plant.",
    "location": "Munich",
    "department": "AI Engineering",
    "skills": [
      {
        "name": "edge_ai",
        "level": 4
      },
      {
        "name": "ml_engineering",
        "level": 4
      }
    ],
    "wills": [
      {
        "name": "experimentation_mindset",
        "level": 5
      },
      {
        "name": "knowledge_sharing",
        "level": 4
      }
    ]
  }
}
```

### 3. Wiki

#### `POST /wiki/list`
List all wiki article paths.

**Request**: `{}`
**Response**:
```json
{
  "sha1": "",
  "paths": [
    "culture.md",
    "people/helene_stutz.md",
    "systems.md"
  ]
}
```

#### `POST /wiki/load`
Load wiki article content.

**Request**:
```json
{
  "file": "culture.md"
}
```
**Response**:
```json
{
  "file": "culture.md",
  "content": "We keep a Wall of Quotes to remember the quirks that make the team fun."
}
```

#### `POST /wiki/search`
Search wiki articles with regex.

**Request**:
```json
{
  "query_regex": "(?i)edge"
}
```
**Response**:
```json
{
  "results": [
    {
      "content": "Edge deployments get a dedicated runbook for support rotations.",
      "linum": 42,
      "path": "systems.md"
    }
  ]
}
```

#### `POST /wiki/update`
Create, update, or delete wiki articles.

**Request**:
```json
{
  "file": "playbooks/edge_rollout.md",
  "content": "Always verify GPU drivers on the line before pushing CV builds.",
  "changed_by": ""
}
```
**Response**: `{}`

### 4. Customers

#### `POST /customers/list`
List customers with pagination.

**Request**:
```json
{
  "offset": 0,
  "limit": 5
}
```
**Response**:
```json
{
  "next_offset": 5,
  "companies": [
    {
      "id": "cust_acme_industrial_systems",
      "name": "Acme Industrial Systems",
      "location": "Munich",
      "deal_phase": "active",
      "high_level_status": "Cautiously optimistic"
    },
    {
      "id": "cust_nordic_logistics_group",
      "name": "Nordic Logistics Group",
      "location": "Amsterdam",
      "deal_phase": "exploring",
      "high_level_status": "Curious"
    }
  ]
}
```

#### `POST /customers/get`
Get full customer record by ID.

**Request**:
```json
{
  "id": "cust_acme_industrial_systems"
}
```
**Response**:
```json
{
  "company": {
    "id": "cust_acme_industrial_systems",
    "name": "Acme Industrial Systems",
    "brief": "Industrial systems supplier modernizing inspection lines.",
    "location": "Munich",
    "primary_contact_name": "Sabine Keller",
    "primary_contact_email": "sabine.keller@acme-industrial.example",
    "deal_phase": "active",
    "high_level_status": "Cautiously optimistic",
    "account_manager": "helene_stutz"
  },
  "found": true
}
```

#### `POST /customers/search`
Search customers by text, phase, or owner.

**Request**:
```json
{
  "query": "logistics",
  "deal_phase": [
    "exploring"
  ],
  "account_managers": [
    "helene_stutz"
  ],
  "locations": [
    "Amsterdam"
  ],
  "limit": 3,
  "offset": 0
}
```
**Response**:
```json
{
  "companies": [
    {
      "id": "cust_nordic_logistics_group",
      "name": "Nordic Logistics Group",
      "location": "Amsterdam",
      "deal_phase": "exploring",
      "high_level_status": "Curious"
    }
  ],
  "next_offset": 3
}
```

### 5. Projects

#### `POST /projects/list`
List projects with pagination.

**Request**:
```json
{
  "offset": 0,
  "limit": 5
}
```
**Response**:
```json
{
  "next_offset": 5,
  "projects": [
    {
      "id": "proj_acme_line3_cv_poc",
      "name": "Line 3 Defect Detection PoC",
      "customer": "cust_acme_industrial_systems",
      "status": "active"
    },
    {
      "id": "proj_nordiclogistics_route_scenario_lab",
      "name": "Routing Scenario Lab",
      "customer": "cust_nordic_logistics_group",
      "status": "exploring"
    }
  ]
}
```

#### `POST /projects/get`
Get detailed project info.

**Request**:
```json
{
  "id": "proj_acme_line3_cv_poc"
}
```
**Response**:
```json
{
  "project": {
    "id": "proj_acme_line3_cv_poc",
    "name": "Line 3 Defect Detection PoC",
    "description": "Computer vision PoC on Line 3 for automated defect detection with edge deployment in the factory.",
    "customer": "cust_acme_industrial_systems",
    "status": "active",
    "team": [
      {
        "employee": "jonas_weiss",
        "time_slice": 0.3,
        "role": "Lead"
      },
      {
        "employee": "lukas_brenner",
        "time_slice": 0.5,
        "role": "Engineer"
      },
      {
        "employee": "felix_baum",
        "time_slice": 0.4,
        "role": "Engineer"
      }
    ]
  },
  "found": true
}
```

#### `POST /projects/search`
Search projects by customer, status, or team.

**Request**:
```json
{
  "query": "defect",
  "customer_id": "cust_acme_industrial_systems",
  "status": [
    "active"
  ],
  "team": {
    "employee_id": "lukas_brenner",
    "role": "Engineer",
    "min_time_slice": 0.3
  },
  "include_archived": false,
  "limit": 5,
  "offset": 0
}
```
**Response**:
```json
{
  "projects": [
    {
      "id": "proj_acme_line3_cv_poc",
      "name": "Line 3 Defect Detection PoC",
      "customer": "cust_acme_industrial_systems",
      "status": "active"
    }
  ],
  "next_offset": 0
}
```

#### `POST /projects/team/update`
Replace project team allocation.

**Request**:
```json
{
  "id": "proj_acme_line3_cv_poc",
  "team": [
    {
      "employee": "lukas_brenner",
      "time_slice": 0.6,
      "role": "Lead"
    },
    {
      "employee": "felix_baum",
      "time_slice": 0.4,
      "role": "Engineer"
    }
  ],
  "changed_by": ""
}
```
**Response**: `{}`

#### `POST /projects/status/update`
Change project status.

**Request**:
```json
{
  "id": "proj_acme_line3_cv_poc",
  "status": "paused",
  "changed_by": ""
}
```
**Response**: `{}`

### 6. Time Tracking

#### `POST /time/log`
Log a new time entry.

**Request**:
```json
{
  "employee": "felix_baum",
  "customer": "cust_acme_industrial_systems",
  "project": "proj_acme_line3_cv_poc",
  "date": "2025-11-15",
  "hours": 7.5,
  "work_category": "customer_project",
  "notes": "CV model training and edge deployment testing",
  "billable": true,
  "status": "draft",
  "logged_by": "helene_stutz"
}
```
**Response**:
```json
{
  "id": "te_001",
  "employee": "felix_baum",
  "customer": "cust_acme_industrial_systems",
  "project": "proj_acme_line3_cv_poc",
  "date": "2025-11-15",
  "hours": 7.5,
  "work_category": "customer_project",
  "notes": "CV model training and edge deployment testing",
  "billable": true,
  "status": "draft"
}
```

#### `POST /time/update`
Update an existing time entry.

**Request**:
```json
{
  "id": "te_001",
  "date": "2025-11-15",
  "hours": 8,
  "work_category": "customer_project",
  "notes": "CV model training, edge deployment testing, and client meeting",
  "billable": true,
  "status": "submitted",
  "changed_by": "helene_stutz"
}
```
**Response**: `{}`

#### `POST /time/get`
Get a single time entry by ID.

**Request**:
```json
{
  "id": "te_001"
}
```
**Response**:
```json
{
  "entry": {
    "employee": "felix_baum",
    "customer": "cust_acme_industrial_systems",
    "project": "proj_acme_line3_cv_poc",
    "date": "2025-11-15",
    "hours": 8,
    "work_category": "customer_project",
    "notes": "CV model training, edge deployment testing, and client meeting",
    "billable": true,
    "status": "draft"
  }
}
```

#### `POST /time/search`
Search time entries with filters.

**Request**:
```json
{
  "employee": "felix_baum",
  "customer": "cust_acme_industrial_systems",
  "project": "proj_acme_line3_cv_poc",
  "date_from": "2025-11-01",
  "date_to": "2025-11-30",
  "work_category": "customer_project",
  "billable": "billable",
  "status": "submitted",
  "limit": 10,
  "offset": 0
}
```
**Response**:
```json
{
  "entries": [
    {
      "id": "te_001",
      "employee": "felix_baum",
      "customer": "cust_acme_industrial_systems",
      "project": "proj_acme_line3_cv_poc",
      "date": "2025-11-15",
      "hours": 8,
      "work_category": "customer_project",
      "notes": "CV model training and edge deployment",
      "billable": true,
      "status": "submitted"
    }
  ],
  "next_offset": 10,
  "total_hours": 40,
  "total_billable": 40,
  "total_non_billable": 0
}
```

#### `POST /time/summary/by-project`
Get time summaries grouped by project.

**Request**:
```json
{
  "date_from": "2025-11-01",
  "date_to": "2025-11-30",
  "customers": [
    "cust_acme_industrial_systems"
  ],
  "projects": [
    "proj_acme_line3_cv_poc"
  ],
  "employees": [
    "felix_baum"
  ],
  "billable": ""
}
```
**Response**:
```json
{
  "summaries": [
    {
      "customer": "cust_acme_industrial_systems",
      "project": "proj_acme_line3_cv_poc",
      "total_hours": 40,
      "billable_hours": 35,
      "non_billable_hours": 5,
      "distinct_employees": 2
    }
  ]
}
```

#### `POST /time/summary/by-employee`
Get time summaries grouped by employee.

**Request**:
```json
{
  "date_from": "2025-11-01",
  "date_to": "2025-11-30",
  "customers": [
    "cust_acme_industrial_systems"
  ],
  "projects": [
    "proj_acme_line3_cv_poc"
  ],
  "employees": [
    "felix_baum"
  ],
  "billable": ""
}
```
**Response**:
```json
{
  "summaries": [
    {
      "employee": "felix_baum",
      "total_hours": 40,
      "billable_hours": 35,
      "non_billable_hours": 5
    }
  ]
}
```

## Sample Agent

```python
import time
from typing import Annotated, List, Union, Literal
from annotated_types import MaxLen, MinLen
from pydantic import BaseModel, Field
from erc3 import erc3 as dev, ApiException, TaskInfo, ERC3
from openai import OpenAI

client = OpenAI()

class NextStep(BaseModel):
    current_state: str
    # we'll use only the first step, discarding all the rest.
    plan_remaining_steps_brief: Annotated[List[str], MinLen(1), MaxLen(5)] =  Field(..., description="explain your thoughts on how to accomplish - what steps to execute")
    # now let's continue the cascade and check with LLM if the task is done
    task_completed: bool
    # Routing to one of the tools to execute the first remaining step
    # if task is completed, model will pick ReportTaskCompletion
    function: Union[
        dev.Req_ProvideAgentResponse,
        dev.Req_ListProjects,
        dev.Req_ListEmployees,
        dev.Req_ListCustomers,
        dev.Req_GetCustomer,
        dev.Req_GetEmployee,
        dev.Req_GetProject,
        dev.Req_GetTimeEntry,
        dev.Req_SearchProjects,
        dev.Req_SearchEmployees,
        dev.Req_LogTimeEntry,
        dev.Req_SearchTimeEntries,
        dev.Req_SearchCustomers,
        dev.Req_UpdateTimeEntry,
        dev.Req_UpdateProjectTeam,
        dev.Req_UpdateProjectStatus,
        dev.Req_UpdateEmployeeInfo,
        dev.Req_TimeSummaryByProject,
        dev.Req_TimeSummaryByEmployee,
    ] = Field(..., description="execute first remaining step")



CLI_RED = "\x1B[31m"
CLI_GREEN = "\x1B[32m"
CLI_BLUE = "\x1B[34m"
CLI_CLR = "\x1B[0m"

def run_agent(model: str, api: ERC3, task: TaskInfo):

    store_api = api.get_erc_dev_client(task)
    about = store_api.who_am_i()

    system_prompt = f"""
You are a business assistant helping customers of Aetherion.

When interacting with Aetherion's internal systems, always operate strictly within the user's access level (Executives have broad access, project leads can write with the projects they lead, team members can read). For guests (public access, no user account) respond exclusively with public-safe data, refuse sensitive queries politely, and never reveal internal details or identities. Responses must always include a clear outcome status and explicit entity links.

To confirm project access - get or find project (and get after finding)
When updating entry - fill all fields to keep with old values from being erased
When task is done or can't be done - Req_ProvideAgentResponse.

# Current user info:
{about.model_dump_json()}
"""
    if about.current_user:
        usr = store_api.get_employee(about.current_user)
        system_prompt += f"\n{usr.model_dump_json()}"

    # log will contain conversation context for the agent within task
    log = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task.task_text},
    ]

    # let's limit number of reasoning steps by 20, just to be safe
    for i in range(20):
        step = f"step_{i + 1}"
        print(f"Next {step}... ", end="")

        started = time.time()

        completion = client.beta.chat.completions.parse(
            model=model,
            response_format=NextStep,
            messages=log,
            max_completion_tokens=16384,
        )

        api.log_llm(
            task_id=task.task_id,
            model=model, # must match slug from OpenRouter
            duration_sec=time.time() - started,
            usage=completion.usage,
        )

        job = completion.choices[0].message.parsed

          # print next sep for debugging
        print(job.plan_remaining_steps_brief[0], f"\n  {job.function}")

        # Let's add tool request to conversation history as if OpenAI asked for it.
        # a shorter way would be to just append `job.model_dump_json()` entirely
        log.append({
            "role": "assistant",
            "content": job.plan_remaining_steps_brief[0],
            "tool_calls": [{
                "type": "function",
                "id": step,
                "function": {
                    "name": job.function.__class__.__name__,
                    "arguments": job.function.model_dump_json(),
                }}]
        })

        # now execute the tool by dispatching command to our handler
        try:
            result = store_api.dispatch(job.function)
            txt = result.model_dump_json(exclude_none=True, exclude_unset=True)
            print(f"{CLI_GREEN}OUT{CLI_CLR}: {txt}")
        except ApiException as e:
            txt = e.detail
            # print to console as ascii red
            print(f"{CLI_RED}ERR: {e.api_error.error}{CLI_CLR}")

            # if SGR wants to finish, then quit loop
        if isinstance(job.function, dev.Req_ProvideAgentResponse):
            print(f"{CLI_BLUE}agent {job.function.outcome}{CLI_CLR}. Summary:\n{job.function.message}")

            for link in job.function.links:
                print(f"  - link {link.kind}: {link.id}")

            break

        # and now we add results back to the convesation history, so that agent
        # we'll be able to act on the results in the next reasoning step.
        log.append({"role": "tool", "content": txt, "tool_call_id": step})
```
