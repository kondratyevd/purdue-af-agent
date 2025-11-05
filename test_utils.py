#!/usr/bin/env python3
"""Test utilities for formatting agent output."""

import json
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

console = Console()


def messages_to_dict(messages):
    """Convert LangChain messages to dict format for serialization."""
    return [msg.model_dump() if hasattr(msg, 'model_dump') else msg.dict() if hasattr(msg, 'dict') else str(msg) for msg in messages]


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


def format_agent_output(output):
    """Format the full agent output; print conversation history first."""
    # Display conversation history first
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

    summary_table.add_row("Status", output.get('status', 'N/A'))
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

