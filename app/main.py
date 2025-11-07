from fastapi import FastAPI, Body
from agent import create_agent_executor
from config import settings
from schemas import AgentOutputState

app = FastAPI()

agent = create_agent_executor()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/query")
async def query(query: str = Body(..., embed=True)) -> AgentOutputState:
    from langchain_core.messages import HumanMessage

    initial_state = {
        "messages": [HumanMessage(content=query)],
        "tool_iteration_count": 0,
    }

    # Account for: classify, agent loop (max_tool_iterations), tools, think, finalize
    # Each iteration: agent -> tools -> think -> agent (3 nodes per iteration)
    recursion_limit = (settings.max_tool_iterations * 3) + 10
    response = agent.invoke(initial_state, config={"recursion_limit": recursion_limit})

    return AgentOutputState(**response)
