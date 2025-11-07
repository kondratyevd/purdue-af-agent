from fastapi import FastAPI, Body, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from agent import create_agent_executor
from config import settings
from schemas import AgentOutputState
from streaming import generate_stream, execute_with_logging

app = FastAPI()
agent = create_agent_executor()


def _get_agent_config():
    """Get agent execution configuration."""
    recursion_limit = (settings.max_tool_iterations * 3) + 10
    return {"recursion_limit": recursion_limit}


def _create_initial_state(query: str):
    """Create initial agent state from query."""
    return {
        "messages": [HumanMessage(content=query)],
        "tool_iteration_count": 0,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/query")
async def query(
    query: str = Body(..., embed=True),
    stream: bool = Query(True, description="Enable streaming mode")
):
    """Process a query with optional streaming."""
    initial_state = _create_initial_state(query)
    config = _get_agent_config()
    
    if stream:
        return StreamingResponse(
            generate_stream(agent, initial_state, config),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        final_state = await execute_with_logging(agent, initial_state, config)
        return AgentOutputState(**final_state)
