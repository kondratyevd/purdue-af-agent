from typing import Optional
from langgraph.graph import StateGraph, END, MessagesState
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from config import settings
from utils import (
    get_current_time,
    get_one_hour_ago,
    safe_parse_time,
    parse_and_format_time,
)




class AgentInputState(MessagesState):
    """Input state for the agent - extends MessagesState with input fields.
    
    Use this for the initial input when invoking the agent.
    Can be extended with additional input fields as needed.
    """
    pass


class AgentState(MessagesState):
    """Main agent state - extends MessagesState for passing messages between nodes.
    
    All agent nodes should use this state type for consistent message handling.
    """
    is_profiling: Optional[bool]  # Classification result for profiling queries
    username: Optional[str]  # Extracted username from profiling query
    start_time: Optional[str]  # Start time for profiling data (ISO format)
    end_time: Optional[str]  # End time for profiling data (ISO format, defaults to now)


# Structured output models - extend BaseModel for LLM structured outputs
class ProfilingQueryClassification(BaseModel):
    """Classifies whether a user query is about profiling or not."""
    is_profiling: bool = Field(description="True if the query is about profiling, performance analysis, CPU usage, or similar performance-related topics")
    confidence: float = Field(description="Confidence score between 0 and 1", ge=0.0, le=1.0)


class ProfilingMetadata(BaseModel):
    """Extracts metadata from profiling queries."""
    username: str = Field(description="Username extracted from the query")
    start_time: Optional[str] = Field(
        description="Start time for profiling data in ISO 8601 format (e.g., '2024-01-01T00:00:00Z'). If not specified in query, use one hour ago.",
        default=None
    )
    end_time: Optional[str] = Field(
        description="End time for profiling data in ISO 8601 format (e.g., '2024-01-01T01:00:00Z'). If not specified in query, use current time.",
        default=None
    )


# Initialize model globally once
_model = init_chat_model(
    model=settings.openai_model,
    temperature=0,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key or None,
)
_model_classifier = _model.with_structured_output(ProfilingQueryClassification)
_model_metadata = _model.with_structured_output(ProfilingMetadata)


# Helper functions
def _get_user_query(state: AgentState) -> str:
    """Extract the last user message from state."""
    return state["messages"][-1].content


def classify_query(state: AgentState) -> AgentState:
    """Classify whether the user query is about profiling."""
    user_query = _get_user_query(state)
    print(f"📥 Received user message: {user_query}")
    
    prompt = f"""Determine if this query is about profiling, performance analysis, CPU usage, memory usage, or similar performance-related topics.

Query: {user_query}"""
    
    classification = _model_classifier.invoke([HumanMessage(content=prompt)])
    print(f"🧠 Classified as profiling: {classification.is_profiling} (confidence: {classification.confidence:.2f})")
    
    return {"is_profiling": classification.is_profiling}


def send_rejection(state: AgentState) -> AgentState:
    """Send rejection message for non-profiling queries."""
    rejection_message = (
        "I'm sorry, but this agent only processes queries related to user profiling, "
        "performance analysis, CPU usage, and similar performance-related topics. "
        "Please ask about profiling data."
    )
    print(f"❌ Sending rejection message for non-profiling query")
    return {"messages": [AIMessage(content=rejection_message)]}


def infer_metadata(state: AgentState) -> AgentState:
    """Extract username and time range from profiling query."""
    user_query = _get_user_query(state)
    now = get_current_time()
    one_hour_ago = get_one_hour_ago()
    now_iso = now.isoformat(timespec='seconds')
    one_hour_ago_iso = one_hour_ago.isoformat(timespec='seconds')
    
    prompt = f"""Extract metadata from this profiling query. Identify:
1. username: The username or user identifier mentioned in the query
2. start_time: The start time for the profiling data window (ISO 8601 format in {settings.timezone} timezone). If not specified in the query, return null/None.
3. end_time: The end time for the profiling data window (ISO 8601 format in {settings.timezone} timezone). If not specified in the query, return null/None.

Current time reference: {now_iso} ({settings.timezone})
One hour ago reference: {one_hour_ago_iso} ({settings.timezone})

Query: {user_query}

Extract the metadata from this query. Only return times if explicitly mentioned in the query. Otherwise return null."""
    
    metadata = _model_metadata.invoke([HumanMessage(content=prompt)])
    
    # Parse LLM-provided times or use defaults
    start_time = safe_parse_time(metadata.start_time, one_hour_ago)
    end_time = safe_parse_time(metadata.end_time, now)
    
    print(f"📊 Extracted metadata: username={metadata.username}, start={start_time}, end={end_time}")
    print(f"🕐 Current time in {settings.timezone}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    return {
        "username": metadata.username,
        "start_time": start_time,
        "end_time": end_time,
    }


def send_profiling_acknowledgement(state: AgentState) -> AgentState:
    """Send acknowledgement message for profiling query."""
    username = state["username"] or "user"
    start_time = state["start_time"]
    end_time = state["end_time"]
    
    # Format times for user-friendly display
    start_formatted = parse_and_format_time(start_time, get_one_hour_ago())
    end_formatted = parse_and_format_time(end_time, get_current_time())
    
    acknowledgement = (
        f"I'll fetch profiling data for user '{username}' "
        f"from {start_formatted} to {end_formatted}. Processing your request..."
    )
    
    print(f"✅ Sending acknowledgement: {acknowledgement}")
    return {"messages": [AIMessage(content=acknowledgement)]}


def should_route(state: AgentState) -> str:
    """Route based on profiling classification."""
    if state.get("is_profiling"):
        return "infer_metadata"
    return "reject"


def create_agent_executor():
    """Create a LangGraph executor with query classification."""
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("classify", classify_query)
    graph.add_node("infer_metadata", infer_metadata)
    graph.add_node("send_acknowledgement", send_profiling_acknowledgement)
    graph.add_node("reject", send_rejection)
    
    # Set entry point
    graph.set_entry_point("classify")
    
    # Route based on classification
    graph.add_conditional_edges(
        "classify",
        should_route,
        {
            "infer_metadata": "infer_metadata",
            "reject": "reject"
        }
    )
    
    # Profiling flow: infer_metadata -> send_acknowledgement -> END
    graph.add_edge("infer_metadata", "send_acknowledgement")
    graph.add_edge("send_acknowledgement", END)
    
    # Rejection flow: reject -> END
    graph.add_edge("reject", END)
    
    compiled = graph.compile()
    return compiled
