from typing import Optional, List, Any, Sequence, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class AgentState(TypedDict):
    """Main agent state - uses TypedDict for passing messages between nodes."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    tool_iteration_count: int
    is_profiling: Optional[bool]
    username: Optional[str]  # Extracted username from profiling query
    start_time: Optional[str]  # ISO time for start
    end_time: Optional[str]  # ISO time for end
    agent_summary: Optional[str]  # Final summary from agent


class ProfilingQueryClassification(BaseModel):
    """Classifies whether a user query is about profiling or not."""

    is_profiling: bool = Field(
        description="True if the query is about profiling, performance analysis, CPU usage, or similar performance-related topics"
    )


class MetadataExtraction(BaseModel):
    """Extracts username and times from the conversation."""

    username: Optional[str] = Field(
        description="Username extracted from the user's message, or None if not found",
        default=None,
    )
    start_time: Optional[str] = Field(
        description="Start time in ISO 8601 format extracted from the conversation, or None if not found",
        default=None,
    )
    end_time: Optional[str] = Field(
        description="End time in ISO 8601 format extracted from the conversation, or None if not found",
        default=None,
    )


class AgentOutputState(BaseModel):
    """Final output schema for API responses or downstream consumers."""

    username: Optional[str] = Field(
        description="Extracted username for the request", default=None
    )
    start_time: Optional[str] = Field(
        description="Final start time in ISO 8601 if available", default=None
    )
    end_time: Optional[str] = Field(
        description="Final end time in ISO 8601 if available", default=None
    )
    agent_summary: str = Field(
        description="Final summary returned by the agent (may include placeholder)",
        default="",
    )
    messages: List[Any] = Field(
        description="Full message chain from the conversation", default_factory=list
    )


class ToolCallFormat(BaseModel):
    """Proper LangChain tool call format."""

    name: str = Field(description="Name of the tool to call")
    args: dict = Field(description="Arguments for the tool call as a dictionary")
    id: str = Field(description="Unique identifier for the tool call")


class ToolCallsExtraction(BaseModel):
    """Extracted tool calls from malformed content."""

    tool_calls: List[ToolCallFormat] = Field(
        description="List of properly formatted tool calls", default_factory=list
    )
