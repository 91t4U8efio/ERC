# ERC3 Dev Agent (Dual Architecture)

This agent is designed for the **ERC3-DEV** benchmark (Aetherion Analytics) using the **Evaluator-Worker Dual Agent** architecture.

## Architecture
- **Evaluator**: Plans the high-level strategy (LiteLLMModel).
- **Worker**: Executes Python code to interact with the API (smolagents.CodeAgent).
- **Coordinator**: Manages the loop and state.

## Setup
1. Ensure you have the `erc3` and `smolagents` libraries installed.
2. Copy `.env` from `store_st` or set `ERC3_API_KEY`, `NEBIUS_API_BASE`, and `NEBIUS_API_KEY`.

## Running
```bash
python submission.py
```
