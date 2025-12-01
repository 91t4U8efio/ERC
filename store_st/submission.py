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
    from erc3 import ERC3, TaskInfo, store, ApiException
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
        # Requirement: Execution logs shown in output log (Coordinator steps)
        print(message, flush=True)
        # Requirement: Store for Evaluator
        self._logs.append(message)

    def log_error(self, message: str):
        # Only store for Evaluator, don't print (since we capture it from stdout)
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
STORE_CONTEXT = """
### 1. STORE ENVIRONMENT & DATA STRUCTURES
The store simulates a fragile API. You must strictly adhere to these JSON schemas and logic constraints.

**A. Product Entity (Returned by `search_products`)**
```json
{
  "sku": "string",       // Unique ID. Use this for basket operations.
  "name": "string",      // Display name. WARNING: Search is fuzzy. You MUST filter this string in Python.
  "price": number,       // Unit price.
  "available": integer   // ESTIMATE ONLY. Real stock is checked at `checkout()`.
}
```
*NOTE*: Products do NOT have descriptions or categories. Infer relevance from `name` and `price`.

**B. Basket Entity (Returned by `get_basket`)**
```json
{
  "items": [             // Can be null if empty
    { "sku": "...", "name": "...", "quantity": int, "price": number }
  ],
  "subtotal": number,
  "total": number,       // Final cost after discounts
  "discount": number,    // Value of discount. WARNING: Can be NULL if no discount applied.
  "coupon": "string"     // The code currently applied.
}
```

### 2. AVAILABLE TOOLS
1. `search_products(query: str)`: Returns `List[Product]`. 
   - **Constraint**: Fuzzy search. Searching "laptop" returns "laptop bag". You MUST filter results using Python logic.
   - **Pagination**: Handled automatically by the tool.
   
2. `get_basket()`: Returns `Basket Entity`.
   - **Usage**: Call at start to check for persistent state. Call after coupon to verify discount.

3. `add_to_basket(sku: str, quantity: int)`: Adds items.
   - **Returns**: Success/Error string.

4. `remove_from_basket(sku: str, quantity: int)`: Removes items.
   - **Usage**: Use to clear basket or fix quantity errors.

5. `apply_coupon(coupon_code: str)`: Applies code.
   - **Constraint**: API only confirms request sent. You MUST call `get_basket()` to verify `discount > 0`.

6. `checkout()`: Finalizes transaction.
   - **The Gatekeeper**: This is the ONLY source of truth for inventory.
   - **Ghost Stock Logic**: If search says 5 available, but checkout fails with "insufficient inventory", the error message will contain the real limit. You must parse this, adjust quantity (remove_from_basket), and retry.

### 3. CRITICAL RULES
- **State Persistence**: The basket is NOT cleared between tasks. Always check `get_basket()` first and empty it if needed.
- **Negative Filtering**: Always filter search results. If looking for "Solo", exclude "Han Solo" or "Solo Cup" based on context.
"""

# ==============================================================================
# TOOL FACTORY
# ==============================================================================
def create_tools(client, logger: ActionLogger):
    
    task_state = {"completed": False}

    # Helper to match the requested log format
    def dispatch_and_log(req, endpoint_path: str):
        # 1. Log Request
        req_data = req.model_dump()
        # Insert the 'tool' key to match the user's trace format
        log_payload = {"tool": endpoint_path, **req_data}
        logger.log(f"    [REQ ->] {json.dumps(log_payload)}")

        # 2. Dispatch with Error Logging
        try:
            resp = client.dispatch(req)
        except Exception as e:
            # CRITICAL FIX: Log the error so the Evaluator sees the "Race Condition" / "Ghost Stock" failure
            logger.log(f"    [<- RESP ERROR] {str(e)}")
            raise e

        # 3. Log Response (if success)
        if hasattr(resp, 'model_dump'):
            resp_data = resp.model_dump()
            logger.log(f"    [<- RESP] {json.dumps(resp_data)}")
        else:
            logger.log(f"    [<- RESP] Success")
            
        return resp

    @tool
    def search_products(query: str) -> List[Dict[str, Any]]:
        """
        Searches for products in the store catalog.
        WARNING: This search is fuzzy! You MUST filter results in Python.
        Args:
            query: The search string (e.g., 'gpu', 'soda').
        """
        if task_state["completed"]:
            return []

        all_items = []
        offset = 0
        current_limit = 10
        
        logger.log(f"  [Tool] Searching for '{query}'...")
        
        while True:
            success = False
            for attempt in range(5):
                try:
                    req = store.Req_ListProducts(query=query, offset=offset, limit=current_limit)
                    # Use our logging wrapper
                    resp = dispatch_and_log(req, "/products/list")
                    
                    success = True
                    
                    batch_items = []
                    if hasattr(resp, 'products') and resp.products:
                        batch_items = resp.products
                    elif hasattr(resp, 'items') and resp.items:
                        batch_items = resp.items
                        
                    if batch_items:
                        items_dict = [item.model_dump() for item in batch_items]
                        all_items.extend(items_dict)
                    
                    if not hasattr(resp, 'next_offset') or resp.next_offset is None or resp.next_offset == -1:
                        return all_items
                    
                    offset = resp.next_offset
                    break 
                    
                except ApiException as e:
                    error_msg = str(e).lower()
                    
                    # Adaptive Pagination Logic - Matches user trace format
                    match = re.search(r"exceeded.*?(\d+).*?>.*?(\d+)", error_msg)
                    if match:
                        max_allowed = int(match.group(2))
                        logger.log(f"    [Adaptive] Limit exceeded. API says max is {max_allowed}. Retrying...")
                        current_limit = max_allowed
                        continue
                    
                    if "invalid pagination" in error_msg or "invalid params" in error_msg:
                        if current_limit > 1:
                            current_limit = 1
                            continue
                        else:
                            return all_items
                    return all_items

            if not success:
                break

        return all_items

    @tool
    def get_basket() -> Dict[str, Any]:
        """Retrieves the current shopping basket."""
        if task_state["completed"]: 
             return {
                "items": None, 
                "subtotal": 0, 
                "total": 0, 
                "discount": 0, 
                "coupon": None,
                "info": "Task completed (Empty View)."
            }
            
        try:
            req = store.Req_ViewBasket()
            resp = dispatch_and_log(req, "/basket/get")
            return resp.model_dump()
        except ApiException as e:
            # We log here too, just in case, though dispatch_and_log catches the API part
            logger.log(f"  [Tool] Error checking basket: {e}")
            return {"error": str(e)}

    @tool
    def add_to_basket(sku: Union[str, int], quantity: int = 1) -> str:
        """
        Adds a product to the shopping basket.
        Args:
            sku: The unique identifier of the product to add.
            quantity: The number of items to add (default 1).
        """
        if task_state["completed"]: return "Error: Task completed."
        try:
            req = store.Req_AddProductToBasket(sku=sku, quantity=quantity)
            dispatch_and_log(req, "/basket/add")
            return f"Success: Added {quantity} x SKU {sku} to basket."
        except ApiException as e:
            return f"Error adding to basket: {e}"

    @tool
    def remove_from_basket(sku: Union[str, int], quantity: int = 1) -> str:
        """
        Removes a product from the shopping basket.
        Args:
            sku: The unique identifier of the product to remove.
            quantity: The number of items to remove (default 1).
        """
        if task_state["completed"]: return "Error: Task completed."
        try:
            req = store.Req_RemoveItemFromBasket(sku=sku, quantity=quantity)
            dispatch_and_log(req, "/basket/remove")
            return f"Success: Removed {quantity} x SKU {sku} from basket."
        except ApiException as e:
            return f"Error removing from basket: {e}"

    @tool
    def apply_coupon(coupon_code: str) -> str:
        """
        Applies a discount coupon to the basket.
        Args:
            coupon_code: The code string of the coupon to apply.
        """
        if task_state["completed"]: return "Error: Task completed."
        try:
            req = store.Req_ApplyCoupon(coupon=coupon_code)
            dispatch_and_log(req, "/coupon/apply")
            return f"Coupon '{coupon_code}' applied. CHECK BASKET TO VERIFY DISCOUNT."
        except ApiException as e:
            return f"Error applying coupon: {e}"

    @tool
    def checkout() -> str:
        """Finalizes the order. Raises error if basket is empty."""
        if task_state["completed"]: return "Order already checked out."
        
        # Silent check to match 'Ghost Stock' logic logic
        try:
            view_req = store.Req_ViewBasket()
            view_resp = client.dispatch(view_req)
            if not view_resp.items:
                return "ERROR: Basket is empty!"
        except Exception:
            pass 

        try:
            req = store.Req_CheckoutBasket()
            # FIX: Capture the response variable!
            resp = dispatch_and_log(req, "/basket/checkout")
            task_state["completed"] = True
            return f"Checkout Success! Receipt: {resp.model_dump()}"
        except Exception as e:
            # The underlying API error is now in the logger via dispatch_and_log
            # We re-raise a clean string for the Agent to catch
            raise Exception(f"Checkout Failed: {e}")

    return [search_products, get_basket, add_to_basket, remove_from_basket, apply_coupon, checkout]

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
        
        # IMPROVEMENT: Prompt explicitly structured using the identified patterns
        # FIX: Updated Playbook A and B to solve logic errors
        self.system_prompt = textwrap.dedent(f"""
            You are the **Evaluator Agent** (The Brain) for an autonomous e-commerce system.
            You direct a **Worker Agent** (The Hands) who executes Python code.
            
            {STORE_CONTEXT}
            
            <PRIME_DIRECTIVES>
            0. **NO CODING**: DO NOT WRITE THE CODE. You define the *Plan*. The Worker writes the *Code*.
            2. **STATE AWARENESS**: The Worker is reset every turn. You must provide all context (SKUs, Quantities, Coupons) in your INSTRUCTION.
            3. **PARAMETERS EXTRACTION**: Exctract all the parameter from logs, if you have all the required data use it in your query to the Worker Agent, don't ask it to make the same requests again.
            4. **TURN EFFICIENCY**: Max 7 turns. Combine non-conflicting steps (e.g., "Add Items AND Apply Coupon").
            5. **FAIL-SAFE**: If a specific item/coupon fails, try synonyms or fallbacks immediately. Do not loop on the same error.
            6. **BRUTEFORCE**: If the task requires bruteforce, provide Worker Agent with all possible options and ask it to implement all of them in one run to have all the data for further considerations. When you observe results of the brutforce, check if all of action actually were considered. Do not ask to checkout when you are askingg for bruteforce.
            7. **FINALZIATION**: Task CANNOT BE COMPLETED PARTIALLY, only full success or imposible to complete. If you have enough info from the Worker Agent, consider if it time to finish.
            8. **COUPONS**: Ignore coupon's description, try to use all of them and check the applicable yourself.
            </PRIME_DIRECTIVES>

            <SEMANTIC_GUARDRAILS>
            - **Synonyms**: If "Monitor" is OOS, check "Display" or "Screen".
            - **"Buy ALL" Logic**: If task says "Buy ALL GPUs" (or similar), instruct Worker to add `item['available']` for quantity, not 1.
            - **Null Safety**: Remind Worker that `basket['discount']` can be None.
            - **Mutually Exclusive Conditions**: If task asks for 'Coupon A AND Coupon B', but API only supports one active coupon, this is IMPOSSIBLE. Do not select the 'best' one. Fail the task.
            </SEMANTIC_GUARDRAILS>

            <STRATEGIC_PLAYBOOKS>
            
            **PLAYBOOK A: THE GHOST STOCK TRAP (Updated)**
            *Trigger*: Search says available, but `checkout()` crashed with "Limit Exceeded" or "Insufficient Inventory".
            *Action*: 
            1. Read the error log from the previous turn to find the *real* limit (often 0).
            2. Instruct Worker: "Remove [X] items from basket to match limit [Y]."
            3. **CRITICAL**: Do NOT instruct to `checkout()` in the same turn. You must wait to see the new basket state. 
               - If an essential item (like "drink" in a "full set") was removed entirely, you must FAIL the task rather than buying an incomplete set.
            
            **PLAYBOOK B: THE CHEAPEST COMBO (Simulation & Report) (Updated)**
            *Trigger*: Goal is "Cheapest X" and multiple pack sizes, accessories, or coupons exist.
            *Action*: Instruct Worker to run a Python simulation:
            1. Discovery: Search for the main product AND all potential accessories/fillers (e.g., search "paper", "cable", "ink").
            2. **EXHAUSTIVE PAIRING**: Do NOT just pick the cheapest accessory. You must iterate through EVERY accessory type.
               - Scenario 1: Main Product + Coupon A
               - Scenario 2: Main Product + Accessory A + Coupon B
               - Scenario 3: Main Product + Accessory B + Coupon B
            3. Execution Loop:
               - Iterate through EVERY configuration in Python.
               - For EACH: Clear Basket -> Add Items -> Test Coupons -> Record Total Price.
            4. **REPORTING**: Find the configuration with the LOWEST total price. Use `print()` to output the exact SKUs, Quantities, and Coupon used.
            5. **WAIT**: Do NOT checkout yet. The Evaluator will read the logs and confirm the best option in the next turn.
            
            **PLAYBOOK C: THE "BUNDLE" COUPON**
            *Trigger*: Coupon name implies a pair (e.g., "COMBO", "PAIR") but discount is 0.
            *Action*:
            1. Instruct Worker to search for cheap filler items (cables, paper).
            2. Add filler -> Apply Coupon -> Check if Total decreases.

            
            **PLAYBOOK D: REQUEST APPLICABITY**
            1. ** If there are no tools that could resolve the request or the request coontradicts with tool capabilities (e.g. implement several coupon in one field simultaniously), then succesful copmletion is impossible.
            </STRATEGIC_PLAYBOOKS>

            <OUTPUT_FORMAT>
            You must output strictly three lines:

            THOUGHT: [Reasoning]
            - Analyze the Previous Turn's logs. Did the last command succeed?
            - Check Basket State. Are we ready to checkout?
            - Select the appropriate Playbook (A, B, or C) if applicable.

            DECISION: [PROCEED | FINISH]
            - Use FINISH only after a successful `checkout()` receipt OR if the task is strictly impossible.

            INSTRUCTION: [The Command for the Worker]
            - Be extremely specific. The Worker Agent needs your instructions to write the code.
            - SHORT, EXPLICIT and MEANINGFUL instructions with all needed parameters and numbers, but WHITHOUT THE CODE.
            </OUTPUT_FORMAT>
        """)

    def decide_next_step(self, history: List[str], basket_state: Dict[str, Any], last_decision: Optional[str] = None) -> str:
        # Change: Get last 4 elements = last 2 full steps (Instruction + Logs for each)
        context_str = "\n".join(history[-4:])
        
        # Build prompt with previous decision if available
        previous_context = ""
        if last_decision:
            previous_context = f"YOUR PREVIOUS TURN DECISION (THOUGHT & INSTRUCTION):\n{last_decision}\n\n"

        # Change: Removed summary history and updated LOGS label
        prompt = (
            f"{self.system_prompt}\n\n"
            f"MAIN TASK: {self.task_description}\n\n"
            f"CURRENT BASKET STATE:\n{json.dumps(basket_state, indent=2)}\n\n"
            f"{previous_context}"
            f"EXECUTION LOGS (Last 2 Steps):\n{context_str}\n\n"
            "Determine the next step."
        )
        
        # Requirement: Show just CURRENT BASKET STATE
        print(f"\n[Evaluator] Current Basket State:\n{json.dumps(basket_state, indent=2)}", flush=True)
        
        # FIX: Explicit status indicator to show user the LLM is thinking (prevent "stuck" perception)
        print("... Evaluator is thinking ...", flush=True)
        try:
            response = self.model(messages=[{"role": "user", "content": prompt}])
        except Exception as e:
            # Fallback if API fails
            print(f"[Evaluator] LLM Call Failed: {e}", flush=True)
            raise e
            
        content = response.content
        
        # Requirement: Show [Evaluator] Decision
        print(f"\n[Evaluator] Decision:\n{content}", flush=True)
        return content

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
        additional_authorized_imports=["math", "json", "time", "re"],
        max_steps=2, 
        verbosity_level=0 # Requirement: Code agent - Show no logging
    )
    return agent

# ==============================================================================
# COORDINATOR LOOP
# ==============================================================================
def run_coordinator(model_id: str, api: ERC3, task: TaskInfo):
    store_client = api.get_store_client(task)
    
    # 1. Initialize Logger and Tools
    logger = ActionLogger()
    tools_list = create_tools(store_client, logger)
    
    evaluator = EvaluatorAgent(model_id, task.task_text)
    
    # Note: Worker is now created inside the loop to be stateless
    
    history = []
    # Change: Removed summary_history list
    last_decision = None # Track the previous decision
    
    print(f"\n>>> COORDINATOR STARTING TASK: {task.task_text}", flush=True)
    
    max_turns = 7 
    for turn in range(max_turns):
        print(f"\n--- TURN {turn + 1} ---", flush=True)
        
        # 0. Clear logs for this turn
        logger.clear()
        
        # 1. Get Basket State
        try:
            basket_req = store.Req_ViewBasket()
            basket_resp = store_client.dispatch(basket_req)
            basket_state = basket_resp.model_dump()
        except Exception as e:
            # If tool returns the "completed" dict manually, it might not be a pydantic model
            # We handle that inside the tool, but here we just need to be safe
            basket_state = {"error": f"Failed to fetch basket: {str(e)}"}

        # 2. Evaluator decides (Passing last_decision)
        # Change: Removed summary_history from call
        decision_text = evaluator.decide_next_step(history, basket_state, last_decision)
        
        # Update last_decision for the NEXT turn
        last_decision = decision_text
        
        # Parse Decision logic to separate Decision from Instruction
        lines = decision_text.split('\n')
        decision_val = "PROCEED"
        for line in lines:
            if line.strip().startswith("DECISION:"):
                decision_val = line.split(":", 1)[1].strip().upper()
                break
        
        if "FINISH" in decision_val:
            print(">>> Evaluator decided to finish.", flush=True)
            return "Success"

        # Parse Instruction
        instruction = ""
        if "INSTRUCTION:" in decision_text:
            parts = decision_text.split("INSTRUCTION:", 1)
            if len(parts) > 1:
                instruction = parts[1].strip()
        
        if not instruction:
            # Fallback if formatting failed but we are proceeding
            instruction = decision_text.split('\n')[-1].strip()

        # 3. Worker executes (Requirement: Show GOAL)
        print(f"\n[Coordinator] GOAL: {instruction}", flush=True)
        
        # FIX: Added Rule #11 to enforce Ghost Stock halt safety
        worker_prompt = (
            f"""{STORE_CONTEXT}

            ROLE:
            Your job is to write code according to GOAL instruction. 
            You should do that defined in the GOAL exactly based on the store environment rules above.

            GOAL: {instruction}
            
            PYTHON CODING RULES (STRICT):
            1. Output valid Python code in a markdown block: ```python ... ```
            2. **HANDLE NONE VALUES**: The API returns `None` for missing values. NEVER do `basket['discount'] > 0`. ALWAYS do `(basket.get('discount') or 0) > 0`.
            3. **NO BARE RAISE**: Do not use `raise` without arguments. Use `raise Exception("Context description")`.
            4. **DEFENSIVE CODING**: When filtering lists, check if the list is empty before accessing index `[0]`.
            5. Use `print()` to log details for the Evaluator.
            6. Use `final_answer('DONE')` to signal completion.
            7. IMPORTANT: Perform ONLY the steps requested in the GOAL. Do NOT assume previous variables exist.
            8. **CHECKOUT SAFETY**: If the GOAL is just `checkout()`, DO NOT add or remove items. Just call `checkout()`.
            9. **CONDITIONAL CHECKOUT**: If the GOAL asks you to verify a condition (like discount > 0) before checking out, and the condition is FALSE, you MUST NOT call `checkout()`.
            10. **PARAMETER CONCISTENCY**: NEVER change parameters that you were provided in the GOAL.
            11. **GHOST STOCK HALT**: If you catch a checkout error regarding inventory and handle it by removing items, DO NOT call `checkout()` again in the same script. Print "Item removed due to stock. Waiting for further instructions." and finish.
            """
        )
        
        try:
            # CRITICAL FIX: Re-create worker every turn to clear internal history/memory.
            # This prevents hallucination where the worker thinks it needs to redo previous steps.
            worker = create_worker_agent(model_id, tools_list)
            
            # Worker runs (silently due to verbosity_level=0)
            # We capture stdout here so we can catch Python errors printed by smolagents
            # (like "Code execution failed..." or "InterpreterError")
            captured_io = io.StringIO()
            with redirect_stdout(captured_io):
                worker.run(worker_prompt)
            
            # Restore output to real stdout so the user still sees it
            worker_output = captured_io.getvalue()
            print(worker_output, flush=True)
            
            # Scan for interpreter errors to feed back to the Evaluator
            # (We skip tool logs because they are already in logger._logs)
            for line in worker_output.splitlines():
                if "Code execution failed" in line or "Exception:" in line or "Traceback" in line:
                    # Simple filter to avoid duplicating tool request/response lines
                    if "[REQ ->]" not in line and "[<- RESP" not in line:
                        logger.log_error(f"    [PYTHON ERROR] {line.strip()}")

            # 4. Construct History for Evaluator
            # CHANGE: We now feed the raw worker output (stdout) to the Evaluator
            # This ensures that if the Worker prints "Best Result is X", the Evaluator actually sees it.
            # Note: worker_output includes ActionLogger prints (API calls) + custom Python prints.
            
            history.append(f"Evaluator Instruction: {instruction}")
            history.append(f"Worker Execution Logs:\n{worker_output}")
            
            # Change: Removed summary history appending
            
        except Exception as e:
            error_msg = f"Worker Error: {e}"
            print(error_msg, flush=True)
            history.append(f"Evaluator Instruction: {instruction}")
            history.append(f"Worker Error: {error_msg}")
            # Change: Removed summary history appending

    return "Max turns reached"

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    MODEL_ID = "nebius/openai/gpt-oss-20b"
    
    if "ERC3_API_KEY" not in os.environ:
        print("ERROR: 'ERC3_API_KEY' is missing. Check your .env file.")
        sys.exit(1)

    print("Initializing ERC3 Session (Dual Agent Mode)...", flush=True)
    try:
        core = ERC3()
        res = core.start_session(
            benchmark="store",
            workspace="my",
            name="egor_fk: Dual Agent Evaluator-Executor non-SGR Architecture - oss-20b",
            architecture="CodeAgent Evaluator-Executor non-SGR"
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
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                run_coordinator(MODEL_ID, core, task)
                break 
            except Exception as e:
                if "RateLimit" in str(e) or "quota" in str(e):
                    wait_time = (attempt + 1) * 5
                    print(f"Hit Rate Limit. Sleeping {wait_time}s before retry...", flush=True)
                    time.sleep(wait_time)
                else:
                    print(f"Non-retriable error: {e}", flush=True)
                    break

        result = core.complete_task(task)
        
        if result.eval:
            score_color = "\033[92m" if result.eval.score == 1.0 else "\033[91m"
            reset = "\033[0m"
            explain = textwrap.indent(result.eval.logs, "  ")
            print(f"\nSCORE: {score_color}{result.eval.score}{reset}")
            print(f"LOGS:\n{explain}\n", flush=True)
        else:
            print("\nTask completed (No evaluation info).", flush=True)

    core.submit_session(res.session_id)
    print("Session Submitted.", flush=True)

if __name__ == "__main__":
    main()
