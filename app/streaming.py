"""Streaming utilities for agent execution."""

import json
import logging
import sys
from schemas import AgentOutputState

logger = logging.getLogger(__name__)


def serialize_message(msg):
    """Serialize a message object to dict format.
    
    Handles both Pydantic v2 (model_dump) and v1 (dict) methods.
    Falls back to str() if neither is available.
    """
    if hasattr(msg, "model_dump"):
        return msg.model_dump()
    elif hasattr(msg, "dict"):
        return msg.dict()
    return str(msg)


def format_sse_chunk(chunk_type: str, content: dict) -> str:
    """Format a chunk as Server-Sent Events (SSE) data line.
    
    Args:
        chunk_type: Type of the chunk (e.g., 'message', 'message_chain', 'final')
        content: Content dictionary to serialize as JSON
        
    Returns:
        Formatted SSE data line: "data: {json}\n\n"
    """
    return f"data: {json.dumps({'type': chunk_type, 'content': content})}\n\n"


def parse_sse_line(line: str):
    """Extract JSON data from an SSE data line.
    
    Args:
        line: SSE data line (e.g., "data: {...}")
        
    Returns:
        Parsed dictionary if valid, None otherwise
    """
    if line.startswith("data: "):
        try:
            return json.loads(line[6:])
        except json.JSONDecodeError:
            return None
    return None


def handle_custom_message(data):
    """Handle custom messages from get_stream_writer - log to server."""
    logger.info(data)
    print(data, file=sys.stderr, flush=True)


def handle_messages_mode(data):
    """Handle messages stream mode - yield individual messages."""
    messages = data if isinstance(data, list) else [data]
    for msg in messages:
        yield format_sse_chunk("message", serialize_message(msg))


def handle_updates_mode(data, final_state):
    """Handle updates stream mode - extract new messages and accumulate state."""
    for node_update in data.values():
        if not isinstance(node_update, dict):
            continue
        
        final_state.update(node_update)
        
        new_messages = node_update.get("messages", [])
        if isinstance(new_messages, list) and new_messages:
            for msg in new_messages:
                try:
                    yield format_sse_chunk("message_chain", serialize_message(msg))
                except Exception as e:
                    logger.error(f"Failed to serialize message: {e}", exc_info=True)


async def execute_with_logging(agent, initial_state, config):
    """Execute agent and capture custom messages for logging (non-streaming mode).
    
    Args:
        agent: The agent executor instance
        initial_state: Initial agent state
        config: Agent execution configuration
        
    Returns:
        Final agent state
    """
    final_state = {}
    
    async for chunk in agent.astream(
        initial_state, config=config, stream_mode=["messages", "custom", "updates"]
    ):
        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue
        
        mode, data = chunk
        
        if mode == "custom":
            handle_custom_message(data)
        elif mode == "updates":
            for node_update in data.values():
                if isinstance(node_update, dict):
                    final_state.update(node_update)
    
    # If no updates were received, get final state via invoke
    if not final_state:
        final_state = agent.invoke(initial_state, config=config)
    
    return final_state


async def generate_stream(agent, initial_state, config):
    """Generate SSE stream from agent execution.
    
    Args:
        agent: The agent executor instance
        initial_state: Initial agent state
        config: Agent execution configuration
    """
    final_state = {}
    
    async for chunk in agent.astream(
        initial_state, config=config, stream_mode=["messages", "custom", "updates"]
    ):
        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue
        
        mode, data = chunk
        
        if mode == "custom":
            handle_custom_message(data)
        elif mode == "messages":
            for sse_chunk in handle_messages_mode(data):
                yield sse_chunk
        elif mode == "updates":
            for sse_chunk in handle_updates_mode(data, final_state):
                yield sse_chunk
    
    # If no updates were received, get final state via invoke
    if not final_state:
        final_state = agent.invoke(initial_state, config=config)
    
    final_output = AgentOutputState(**final_state)
    yield format_sse_chunk("final", final_output.model_dump())

