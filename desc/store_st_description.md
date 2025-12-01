# ERC3 Evaluator-Worker Architecture & Tooling

This document outlines the Dual-Agent Architecture used to solve the simulated e-commerce environment (ERC3). The system separates high-level strategic reasoning (**The Evaluator**) from technical code execution (**The Worker**) to handle a fragile API, "ghost stock" inventory issues, and complex optimization tasks (e.g., "cheapest combo").

## 1. System Architecture

The solution uses a Coordinator Loop that manages two distinct agents. The cycle repeats for a maximum of 7 turns per task.

### 1.1 The Evaluator ("The Brain")
- **Implementation**: `LiteLLMModel` (Direct LLM calls using nebius/openai/gpt-oss-120b).
- **Role**: Analyzes the conversation history, current basket state, and previous tool outputs. It never writes code.
- **Output**: Generates a structured response:
    - `THOUGHT`: Reasoning based on logs and basket state.
    - `DECISION`: `PROCEED` or `FINISH`.
    - `INSTRUCTION`: A specific natural language goal for the Worker (e.g., "Search for 'monitor', filter for synonyms, and add 2 to basket").
- **Prime Directives**:
    - **State Awareness**: Must provide all context (SKUs, Quantities) in every instruction as the Worker has no memory of previous turns.
    - **Fail-Safe**: If a specific item fails, immediately switch to synonyms or fallbacks.
    - **Brute Force**: If optimization is required, instruct the Worker to run a Python simulation rather than guessing.

### 1.2 The Worker ("The Hands")
- **Implementation**: `smolagents.CodeAgent`.
- **Role**: Receives the `INSTRUCTION` from the Evaluator and converts it into executable Python code.
- **Capabilities**: Can write loops, perform regex filtering, and handle API pagination logic.
- **Constraint**: **Stateless**. The Worker is re-initialized every turn to prevent "hallucination" of previous variable states. It executes only the immediate goal.

### 1.3 The Orchestrator (Coordinator Loop)
- Fetches the `basket_state` at the start of every turn (**Source of Truth**).
- Parses the Evaluator's response.
- Captures tool outputs via a custom `ActionLogger`.
- Injects execution logs back into the Evaluator's context window.

## 2. Strategic Playbooks

The Evaluator is programmed with specific "Playbooks" to handle complex environment scenarios:

### Playbook A: The Ghost Stock Trap
- **Trigger**: Search indicates items are available (e.g., `available: 5`), but `checkout()` crashes with a "Limit Exceeded" error.
- **Strategy**:
    1. Evaluator reads the error log from the previous turn to find the real limit returned by the API.
    2. Instructs Worker: "Remove [X] items from basket to match limit [Y], then Checkout."

### Playbook B: The Cheapest Combo (Brute Force)
- **Trigger**: Goal is "Cheapest X" and multiple pack sizes or coupons exist.
- **Strategy**: Instruct Worker to run a self-contained Python simulation:
    - **Discovery**: Search for all available pack sizes.
    - **Permutation**: Calculate every valid combination to meet the target quantity.
    - **Execution Loop**: Iterate through every configuration in Python: `Clear Basket` -> `Add Items` -> `Bruteforce EVERY available coupon`.
    - **Finalize**: Re-build the winning configuration (lowest price) and checkout.

### Playbook C: The "Bundle" Coupon
- **Trigger**: A coupon name implies a pair (e.g., "COMBO") but applying it results in $0 discount.
- **Strategy**:
    - Search for cheap filler items (cables, paper).
    - `Add filler` -> `Apply Coupon` -> `Check if Total decreases`.

## 3. Store Data Structures (Entities)

The agents operate on strict JSON schemas returned by the API.

### 3.1 Product Entity
Returned by `search_products`.
- **Constraint**: No description or category. Relevance is inferred strictly from name and price.
- **Fuzzy Search**: The API is fuzzy (searching "laptop" returns "laptop bag"). The Worker must implement Python-side filtering to exclude irrelevant matches.

```json
{
  "sku": "gpu-h100",
  "name": "NVidia H100", 
  "price": 20000,
  "available": 3  // ESTIMATE ONLY. 'checkout()' is the source of truth.
}
```

### 3.2 Basket Entity
Returned by `get_basket`. Persists across steps.

```json
{
  "items": [ ... ],
  "subtotal": 40000,
  "total": 40000,
  "discount": 0,    // MUST check this > 0 to verify coupon success
  "coupon": "SAVE10"
}
```

## 4. Robust Toolset

The Worker agent interacts with the store via custom tool wrappers defined in `submission.py`:

- **`search_products(query)`**:
    - **Adaptive Pagination**: Automatically catches `LimitExceeded` errors, parses the max limit from the error message using Regex, and retries the request with the correct limit.

- **`checkout()`**:
    - **The Gatekeeper**: The only true check for inventory. If it fails, it raises an exception that triggers Playbook A.

- **`apply_coupon(code)`**:
    - **Verification**: The API only confirms the request was sent. The Worker must check `basket['discount']` to confirm it actually worked.

