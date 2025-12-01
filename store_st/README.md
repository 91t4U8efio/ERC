# ERC3 Dual-Agent E-Commerce Solver

This project implements an autonomous dual-agent system designed to solve complex e-commerce tasks within the **ERC3 Benchmark** environment. The system utilizes a "Coordinator-Worker" architecture where a high-level **Evaluator Agent** plans the strategy and a low-level **Worker Agent** executes Python code to interact with the store API.

## Architecture

The system splits responsibilities between two distinct agents to maximize reliability and logic adherence:

### 1. The Evaluator (The Brain)

-   **Role:** Planner and Strategist.
    
-   **Model:** Powered by `nebius/openai/gpt-oss-120b` (via LiteLLM).
    
-   **Function:** It analyzes the current basket state and execution logs to determine the next logical step. It **does not** write code.
    
-   **Logic:** Operates on strict "Prime Directives" and "Strategic Playbooks" to handle edge cases like:
    
    -   **Ghost Stock:** Detects when the API reports false availability and adjusts quantities based on error logs.
        
    -   **Cheapest Combo:** Simulates multiple basket configurations to find the lowest price before checking out.
        
    -   **Bundle Coupons:** Identifies and satisfies dependencies for specific coupons.
        

### 2. The Worker (The Hands)

-   **Role:** Executor.
    
-   **Framework:** Built on `smolagents` (CodeAgent).
    
-   **Function:** Receives natural language instructions from the Evaluator and translates them into executable Python code.
    
-   **Tools:** Has access to a suite of simulated store tools:
    
    -   `search_products(query)`: Fuzzy search with adaptive pagination.
        
    -   `get_basket()`: Retrieves current cart state.
        
    -   `add_to_basket(sku, quantity)`
        
    -   `remove_from_basket(sku, quantity)`
        
    -   `apply_coupon(code)`
        
    -   `checkout()`: The final gatekeeper method.
        

## Prerequisites

-   Python 3.10+
    
-   The `erc3` benchmark library
    
-   `smolagents` library
    
-   `python-dotenv` for environment management
    

## Installation

1.  **Clone the repository:**
    
    ```
    git clone <repository-url>
    cd <repository-directory>
    
    ```
    
2.  Install dependencies:
    
    The script explicitly checks for the following packages:
    
    ```
    pip install smolagents erc3 python-dotenv
    
    ```
    

## Configuration

Create a `.env` file in the root directory to store your API credentials. The script requires the following variables:

```
# .env file

# API Key for the ERC3 Benchmark Environment
ERC3_API_KEY=your_erc3_key_here

# API Base and Key for the LLM Provider (e.g., Nebius, OpenAI compatible)
NEBIUS_API_BASE=[https://api.studio.nebius.ai/v1/](https://api.studio.nebius.ai/v1/)
NEBIUS_API_KEY=your_nebius_api_key_here

```

## 🚀 Usage

To start the agent and run through the assigned tasks:

```
python submission.py

```

### Execution Flow

1.  **Initialization:** The script connects to the ERC3 session using the credentials provided.
    
2.  **Task Loop:** It iterates through all assigned tasks in the benchmark.
    
3.  **Coordinator Loop:** For each task, the Coordinator runs a maximum of 7 turns:
    
    -   **Log Clearing:** Resets logs for the new turn.
        
    -   **State Fetch:** Gets the current basket.
        
    -   **Evaluation:** The Evaluator decides the next move (e.g., "Search for laptops" or "Apply coupon SAVE20").
        
    -   **Execution:** The Worker writes Python code to perform the action.
        
    -   **Feedback:** Output is captured and fed back to the Evaluator for the next turn.
        
4.  **Completion:** Once the Evaluator signals "FINISH" or `checkout()` succeeds, the task is submitted.
    

## Key Features & Strategies

-   **Robust Error Handling:** The script captures `stdout` to catch Python interpreter errors and feed them back to the LLM, allowing the agent to "fix" its own code in the next turn.
    
-   **Adaptive Pagination:** The `search_products` tool automatically handles API limits and pagination logic so the LLM doesn't have to.
    
-   **State Persistence:** The system is aware that the basket state persists between turns, preventing redundant "add to cart" actions.
    
-   **Safety Guardrails:**
    
    -   **No Infinite Loops:** Max 7 turns per task.
        
    -   **Rate Limiting:** Implements exponential backoff for API rate limits.
        
    -   **Inventory Checks:** Prevents checkout if the basket is empty or if "Ghost Stock" logic is triggered.
