from fastapi import FastAPI
from pydantic import BaseModel
from agent import create_agent_executor

app = FastAPI()

agent = create_agent_executor()


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    response: str
    status: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/query")
async def query(request: QueryRequest) -> QueryResponse:
    from langchain_core.messages import HumanMessage
    
    response = agent.invoke({"messages": [HumanMessage(content=request.query)]}, config={"recursion_limit": 20})
    
    messages = response["messages"]
    last_message = messages[-1]
    content = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    return QueryResponse(query=request.query, response=content, status="success")
