#!/usr/bin/env python3
"""Test utilities for formatting agent output."""

import json
import sys
import os
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

# Add app directory to path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
from streaming import serialize_message, parse_sse_line

console = Console()


def messages_to_dict(messages):
    """Convert LangChain messages to dict format for serialization."""
    return [serialize_message(msg) for msg in messages]


def format_message_content(message_dict):
    """Convert message dict content to displayable string."""
    parts = []
    
    # Handle content field
    content = message_dict.get('content', '')
    if isinstance(content, str):
        if content:
            parts.append(content)
    elif isinstance(content, list):
        # Handle complex content like tool calls (Anthropic format)
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    parts.append(item.get('text', ''))
                elif item.get('type') == 'tool_use':
                    parts.append(f"\n🔧 Tool Call: {item.get('name', 'unknown')}")
                    parts.append(f"   Args: {json.dumps(item.get('input', {}), indent=2)}")
                    parts.append(f"   ID: {item.get('id', 'N/A')}")
    else:
        parts.append(str(content))
    
    # Handle tool_calls attached to the message (OpenAI format)
    tool_calls = message_dict.get('tool_calls', [])
    if tool_calls:
        for tool_call in tool_calls:
            parts.append(f"\n🔧 Tool Call: {tool_call.get('name', 'unknown')}")
            parts.append(f"   Args: {json.dumps(tool_call.get('args', {}), indent=2)}")
            parts.append(f"   ID: {tool_call.get('id', 'N/A')}")
    
    return "\n".join(parts) if parts else "(empty)"


def format_message_dict(message_dict):
    """Format a single message dict with Rich formatting."""
    msg_type = message_dict.get('type', '').replace('Message', '').replace('message', '')
    content = format_message_content(message_dict)
    
    # Map message types to display names and colors
    type_map = {
        'human': ('🧑 Human', 'blue'),
        'ai': ('🤖 Assistant', 'green'),
        'assistant': ('🤖 Assistant', 'green'),
        'tool': ('🔧 Tool Output', 'yellow'),
        'system': ('⚙️  System', 'magenta'),
        '': ('📝 Unknown', 'white'),
    }
    
    title, border_style = type_map.get(msg_type.lower(), ('📝 Unknown', 'white'))
    
    console.print(Panel(content, title=title, border_style=border_style))


def format_messages(messages):
    """Format and display a list of message dicts with Rich formatting."""
    if not messages:
        console.print("[dim]No messages in conversation[/dim]")
        return
    
    for msg in messages:
        format_message_dict(msg)
        console.print()  # Add spacing between messages


def format_agent_output(output, skip_conversation_history=False):
    """Format the full agent output.
    
    Args:
        output: Agent output dictionary
        skip_conversation_history: If True, skip printing conversation history
                                  (useful for streaming mode where messages are already displayed)
    """
    # Display conversation history first (unless skipped)
    if not skip_conversation_history:
        messages = output.get('messages', [])
        if messages:
            console.print(Panel(
                f"Conversation History ({len(messages)} messages)",
                title="💬 Conversation History",
                border_style="bold blue"
            ))
            console.print()
            format_messages(messages)
        else:
            console.print("[dim]No conversation history available[/dim]")
        console.print()

    # Then display summary and metadata
    summary_table = Table(title="Agent Output Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Field", style="cyan", no_wrap=True)
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Username", output.get('username', 'N/A') or 'None')
    summary_table.add_row("Start Time", output.get('start_time', 'N/A') or 'None')
    summary_table.add_row("End Time", output.get('end_time', 'N/A') or 'None')

    console.print(summary_table)
    console.print()

    # Finally display agent summary
    agent_summary = output.get('agent_summary', '')
    if agent_summary:
        console.print(Panel(
            agent_summary,
            title="📋 Agent Summary",
            border_style="bold green",
            padding=(1, 2)
        ))
        console.print()


def format_message(message):
    """Alias for format_message_dict for backward compatibility."""
    return format_message_dict(message)


def _is_new_message(msg_id: str, accumulated_messages: List[dict]) -> bool:
    """Check if a message ID is new (not in accumulated messages)."""
    existing_ids = [m.get("id") if isinstance(m, dict) else str(m) for m in accumulated_messages]
    return msg_id not in existing_ids


def process_sse_stream(response) -> Dict[str, Any]:
    """Process SSE stream and return accumulated messages and final output."""
    accumulated_messages = []
    final_output = None
    buffer = ""
    
    for line in response.iter_lines(decode_unicode=True):
        if line:
            buffer += line + "\n"
        elif buffer:  # Empty line indicates end of SSE event
            for sse_line in buffer.strip().split("\n"):
                data = parse_sse_line(sse_line)
                if not data:
                    continue
                
                chunk_type = data.get("type")
                content = data.get("content")
                
                if chunk_type == "message_chain" and isinstance(content, dict):
                    console.print()
                    format_message_dict(content)
                    accumulated_messages.append(content)
                
                elif chunk_type == "message" and isinstance(content, dict):
                    msg_id = content.get("id") or str(content)
                    if _is_new_message(msg_id, accumulated_messages):
                        accumulated_messages.append(content)
                        if content.get("type") and ("content" in content or "text" in content):
                            console.print()
                            format_message_dict(content)
                
                elif chunk_type == "final":
                    final_output = content
            
            buffer = ""
    
    return final_output or {
        "messages": accumulated_messages,
        "agent_summary": "",
        "username": None,
        "start_time": None,
        "end_time": None,
    }


def generate_diagram():
    """Generate and save a mermaid diagram of the agent graph."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
    from agent import create_agent_executor
    
    agent = create_agent_executor()
    graph_img = agent.get_graph().draw_mermaid_png()
    
    output_path = "agent_diagram.png"
    with open(output_path, "wb") as f:
        f.write(graph_img)
    print(f"📊 Agent diagram saved to {output_path}")


def display_user_query(query: str):
    """Display the user query as a human message."""
    human_message = {"type": "human", "content": query}
    console.print()
    format_message_dict(human_message)


def run_test_script(script_name: str, test_agent_func):
    """Common main execution block for test scripts.
    
    Args:
        script_name: Name of the script (e.g., 'test_streaming.py')
        test_agent_func: Function that takes a query string and returns the result
    """
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: python {script_name} <query>")
        print("\nGenerating agent diagram...")
        generate_diagram()
        sys.exit(0)
    
    print("Generating agent diagram...")
    generate_diagram()
    print()
    
    query = sys.argv[1]
    result = test_agent_func(query)
    format_agent_output(result)

