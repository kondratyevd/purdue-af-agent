from typing_extensions import Literal
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from config import settings
from prompts import (
    CLASSIFICATION_PROMPT,
    GLOBAL_SYSTEM_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    THINK_REFLECTION_PROMPT_TEMPLATE,
    FINALIZE_OUTPUT_PROMPT,
)
from tools import TOOLS, TOOLS_BY_NAME, think_tool
from schemas import (
    AgentState,
    AgentOutputState,
    ProfilingQueryClassification,
    MetadataExtraction,
)
from utils import validate_and_fix_tool_calls

# Initialize model globally once
_model = init_chat_model(
    model=settings.openai_model,
    model_provider="openai",
    temperature=0,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key or None,
)
_model_classifier = _model.with_structured_output(ProfilingQueryClassification)
_model_with_tools = _model.bind_tools(TOOLS)
_model_metadata_extractor = _model.with_structured_output(MetadataExtraction)


def classify_query(state: AgentState) -> AgentState:
    """Classify whether the user query is about profiling."""
    print("🔍 Classifying query...")
    classification = _model_classifier.invoke(
        [SystemMessage(content=CLASSIFICATION_PROMPT)] + state["messages"]
    )
    print(f"🧠 Classified as profiling: {classification.is_profiling}")
    return {"is_profiling": classification.is_profiling}


def agent_llm(state: AgentState) -> AgentState:
    """Analyze current state and decide on next actions."""
    messages = state["messages"]

    # Add global system prompt if not already present
    has_global_prompt = any(
        isinstance(msg, SystemMessage) and msg.content == GLOBAL_SYSTEM_PROMPT
        for msg in messages
    )
    system_prompt_msg = None
    if not has_global_prompt:
        system_prompt_msg = SystemMessage(content=GLOBAL_SYSTEM_PROMPT)
        messages = [system_prompt_msg] + messages

    # Invoke model and validate tool calls
    print(f"🤖 Invoking agent LLM (ctx={len(messages)} msgs)")
    ai_msg = validate_and_fix_tool_calls(
        _model_with_tools.invoke(
            [SystemMessage(content=METADATA_EXTRACTION_PROMPT)] + messages
        )
    )

    if ai_msg.tool_calls:
        print(
            f"✅ Agent made {len(ai_msg.tool_calls)} tool call(s): {[tc.get('name') for tc in ai_msg.tool_calls]}"
        )

    return {"messages": [system_prompt_msg, ai_msg] if system_prompt_msg else [ai_msg]}


def tool_node(state: AgentState) -> AgentState:
    """Execute all tool calls from the previous LLM response."""
    tool_calls = state["messages"][-1].tool_calls
    print(f"🔧 Executing {len(tool_calls)} tool call(s)")

    # Filter out invalid tool calls and execute valid ones
    valid_tool_calls = []
    observations = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        if tool_name not in TOOLS_BY_NAME:
            print(f"  ⚠️  Skipping unknown tool: {tool_name}")
            observations.append(
                f"Error: Tool '{tool_name}' does not exist. Available tools: {', '.join(TOOLS_BY_NAME.keys())}"
            )
            valid_tool_calls.append(tool_call)
        else:
            try:
                result = TOOLS_BY_NAME[tool_name].invoke(tool_call["args"])
                observations.append(result)
                valid_tool_calls.append(tool_call)
            except Exception as e:
                print(f"  ✗ Error executing {tool_name}: {e}")
                observations.append(f"Error executing {tool_name}: {str(e)}")
                valid_tool_calls.append(tool_call)

    # Create tool message outputs
    tool_outputs = [
        ToolMessage(
            content=observation, name=tool_call["name"], tool_call_id=tool_call["id"]
        )
        for observation, tool_call in zip(observations, valid_tool_calls)
    ]

    return {
        "messages": tool_outputs,
        "tool_iteration_count": state["tool_iteration_count"] + 1,
    }


def think_node(state: AgentState) -> AgentState:
    """Automatically call think_tool to reflect on tool results."""
    messages = state["messages"]

    # Find the last ToolMessage (skip if it was think_tool to avoid loops)
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    if not tool_messages or tool_messages[-1].name == "think_tool":
        return {}

    last_tool_msg = tool_messages[-1]
    print(f"🤔 Reflecting on tool execution: {last_tool_msg.name}")

    # Generate reflection using LLM
    reflection = _model.invoke(
        [
            SystemMessage(
                content=THINK_REFLECTION_PROMPT_TEMPLATE.format(
                    tool_name=last_tool_msg.name,
                    tool_result=last_tool_msg.content,
                    available_tools=", ".join(TOOLS_BY_NAME.keys()),
                )
            )
        ]
        + messages
    ).content

    # Call think_tool and return as ToolMessage
    return {
        "messages": [
            ToolMessage(
                content=think_tool.invoke({"reflection": reflection}),
                name="think_tool",
                tool_call_id=f"think_{state['tool_iteration_count']}",
            )
        ],
    }


def finalize_output(state: AgentState) -> AgentState:
    """Use LLM to construct final summary based on agent's work."""
    print(f"📝 Finalizing output (ctx={len(state['messages'])} msgs)")
    messages = state["messages"]

    # Extract metadata from the final conversation state
    metadata = _model_metadata_extractor.invoke(messages)
    print(
        f"📊 Extracted: username={metadata.username}, start={metadata.start_time}, end={metadata.end_time}"
    )

    # Use existing values if already set, otherwise use extracted
    username = state.get("username") or metadata.username
    start_time = state.get("start_time") or metadata.start_time
    end_time = state.get("end_time") or metadata.end_time
    print(f"📊 Final: username={username}, start={start_time}, end={end_time}")

    # Build explicit context with the FINAL extracted values
    state_context = []
    if username:
        state_context.append(f"FINAL extracted username: {username}")
    if start_time:
        state_context.append(f"FINAL extracted start_time: {start_time}")
    if end_time:
        state_context.append(f"FINAL extracted end_time: {end_time}")

    context_prompt = FINALIZE_OUTPUT_PROMPT
    if state_context:
        context_prompt += (
            "\n\n**CRITICAL: Use ONLY these final extracted values in your summary. Do not reference intermediate or incorrect dates from the conversation. The summary must match these exact values:**\n"
            + "\n".join(state_context)
        )

    # Generate summary
    response = _model.invoke([SystemMessage(content=context_prompt)] + messages)
    summary = response.content

    return {
        "agent_summary": summary,
        "username": username,
        "start_time": start_time,
        "end_time": end_time,
    }


def send_rejection(state: AgentState) -> AgentState:
    """Send rejection message for non-profiling queries."""
    print("❌ Sending rejection message for non-profiling query")
    return {
        "agent_summary": (
            "This agent only processes profiling/performance queries. "
            "Please ask about profiling data."
        ),
    }


def routing_after_classify(state: AgentState) -> Literal["agent", "reject"]:
    """After classification, route to agent or rejection."""
    if state["is_profiling"]:
        print("➡️  agent")
        return "agent"
    print("➡️  reject")
    return "reject"


def routing_after_agent_decision(state: AgentState) -> Literal["tools", "finalize"]:
    """After agent LLM, route to tools if it made tool calls, otherwise finalize."""
    messages = state["messages"]

    # Find the last AIMessage
    last_ai_msg = next(
        (msg for msg in reversed(messages) if isinstance(msg, AIMessage)), None
    )

    # Check max iterations before allowing more tool calls
    current_count = state["tool_iteration_count"]
    if current_count >= settings.max_tool_iterations:
        print(f"⛔ Max iterations ({settings.max_tool_iterations}) reached")
        return "finalize"

    if last_ai_msg and last_ai_msg.tool_calls:
        print(f"➡️  tools (iter {current_count + 1}/{settings.max_tool_iterations})")
        return "tools"

    print("➡️  finalize")
    return "finalize"


def create_agent_executor():
    """Create a LangGraph executor with query classification and tool loop."""
    graph = StateGraph(AgentState, output_schema=AgentOutputState)

    # Nodes
    graph.add_node("classify_query", classify_query)
    graph.add_node("agent", agent_llm)
    graph.add_node("tools", tool_node)
    graph.add_node("think", think_node)
    graph.add_node("finalize", finalize_output)
    graph.add_node("reject", send_rejection)

    # Edges
    graph.add_edge(START, "classify_query")
    graph.add_conditional_edges(
        "classify_query", routing_after_classify, {"agent": "agent", "reject": "reject"}
    )
    graph.add_conditional_edges(
        "agent",
        routing_after_agent_decision,
        {
            "tools": "tools",
            "finalize": "finalize",
        },
    )
    graph.add_edge("tools", "think")
    graph.add_edge("think", "agent")
    graph.add_edge("finalize", END)
    graph.add_edge("reject", END)

    compiled = graph.compile()
    return compiled
