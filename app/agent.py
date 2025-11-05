from typing_extensions import Literal
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from config import settings
from prompts import (
    GLOBAL_SYSTEM_PROMPT,
    PLANNING_PROMPT,
    PLAN_ANALYSIS_PROMPT_TEMPLATE,
    METADATA_EXTRACTION_PROMPT,
    FINALIZE_OUTPUT_PROMPT,
)
from tools import TOOLS, TOOLS_BY_NAME, AVAILABLE_TOOL_NAMES
from schemas import (
    AgentState,
    AgentOutputState,
    ProfilingQueryClassification,
    FinalizeOutput,
    MetadataExtraction,
    AgentReasoning,
    PlanAnalysisResult,
)

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
_model_reasoning = _model.with_structured_output(AgentReasoning)
_model_finalize = _model.with_structured_output(FinalizeOutput)
_model_plan_analysis = _model.with_structured_output(PlanAnalysisResult)


def classify_query(state: AgentState) -> AgentState:
    """Classify whether the user query is about profiling."""
    classification = _model_classifier.invoke([
        SystemMessage(content="Determine if the user's message is about profiling, performance analysis, CPU/memory usage, or similar.")
    ] + state["messages"])
    print(f"🧠 Classified as profiling: {classification.is_profiling} (confidence: {classification.confidence:.2f})")
    
    return {"is_profiling": classification.is_profiling}


def send_rejection(state: AgentState) -> AgentState:
    """Send rejection message for non-profiling queries as structured output."""
    print(f"❌ Sending rejection message for non-profiling query")
    return {
        "agent_summary": (
            "This agent only processes profiling/performance queries. "
            "Please ask about profiling data."
        ),
        "status": "rejected",
    }


def generate_plan(state: AgentState) -> AgentState:
    """Generate a plan for tool usage based on the user query and available tools."""
    messages = state["messages"]
    plan_content = (_model.invoke([SystemMessage(content=PLANNING_PROMPT)] + messages).content or "")
    
    print(f"📋 Generated plan: {plan_content[:200]}...")
    
    return {
        "plan": plan_content,
    }

def analyze_plan(state: AgentState) -> AgentState:
    """Analyze the generated plan and check if all required tools are available."""
    plan = state.get("plan")
    if not plan:
        return {}
    
    result = _model_plan_analysis.invoke([SystemMessage(content=PLAN_ANALYSIS_PROMPT_TEMPLATE.format(plan=plan))])
    print(f"🔍 Plan analysis: {result.decision}")
    if result.decision == "MISSING_TOOLS":
        print(f"⚠️  Missing tools detected")
        return {
            "agent_summary": f"MISSING_TOOLS: {(result.details or 'Required tools are not available.').strip()}",
            "status": "failure",
            "tools_missing": True,
        }
    print(f"✅ All tools available")
    return {
        "messages": [SystemMessage(content=f"APPROVED PLAN:\n{plan}\n\nFollow this plan step by step. Use actual tool execution results, not example values from the plan.")],
        "tools_missing": False,
    }


def add_system_message(state: AgentState) -> AgentState:
    """Add general system instructions for the agent."""
    print(f"📋 Adding global system message to conversation")
    return {
        "messages": [SystemMessage(content=GLOBAL_SYSTEM_PROMPT)],
    }


def agent_llm(state: AgentState) -> AgentState:
    """Analyze current state and decide on next actions."""
    messages = state["messages"]
    messages_with_prompt = [SystemMessage(content=METADATA_EXTRACTION_PROMPT)] + messages
    
    print(f"🤖 LLM ctx={len(messages_with_prompt)}")
    
    # Get reasoning: reflect on what agent knows and what it plans to achieve
    pre_reasoning = _model_reasoning.invoke([
        SystemMessage(content="Provide exactly two sentences: First, reflect on what information you already know from the conversation. Second, describe what you plan to achieve with the next tool call (if any), or what conclusion you have reached if no tool call is needed."),
    ] + messages)
    print(f"💭 {pre_reasoning.reasoning}")
    pre_reasoning_msg = AIMessage(content=pre_reasoning.reasoning)
    
    # Use native tool binding for proper tool call format
    ai_msg = _model_with_tools.invoke(messages_with_prompt + [pre_reasoning_msg])
    
    tool_calls = ai_msg.tool_calls if isinstance(ai_msg, AIMessage) else None
    if tool_calls:
        tool_names = [tc.get("name", "unknown") for tc in tool_calls]
        print(f"🔧 tool_calls={len(tool_calls)}: {tool_names}")
    else:
        print(f"🔧 tool_calls=0 (text response)")
    
    # Extract metadata from conversation
    metadata = _model_metadata_extractor.invoke(messages + [pre_reasoning_msg, ai_msg])
    
    # Use existing username if already set, otherwise use extracted
    username = state.get("username") or metadata.username
    if metadata.username and not state.get("username"):
        print(f"📊 Extracted username: {metadata.username}")
    
    return {
        "messages": [pre_reasoning_msg, ai_msg],
        "start_time": metadata.start_time,
        "end_time": metadata.end_time,
        "username": username,
    }


def tool_node(state: AgentState) -> AgentState:
    """Execute all tool calls from the previous LLM response."""
    tool_calls = state["messages"][-1].tool_calls
    
    if not tool_calls:
        return {}

    # Increment tool iteration count
    new_count = state["tool_iteration_count"] + 1
    print(f"🧮 tools={len(tool_calls)} iter={new_count}/{settings.max_tool_iterations}")
    
    # Execute all tool calls
    observations = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        print(f"🔧 calling tool: {tool_name}")
        
        # Check if tool exists
        if tool_name not in TOOLS_BY_NAME:
            error_msg = (
                f"ERROR: Tool '{tool_name}' does not exist. "
                f"Available tools are: {AVAILABLE_TOOL_NAMES}. "
                f"Please use one of the available tools or provide a text response instead."
            )
            print(f"❌ {error_msg}")
            observations.append(error_msg)
        else:
            tool = TOOLS_BY_NAME[tool_name]
            args = tool_call["args"]
            
            try:
                observations.append(tool.invoke(args))
            except Exception as e:
                error_msg = f"ERROR: Invalid arguments for tool '{tool_name}': {str(e)}. Args provided: {args}"
                print(f"❌ {error_msg}")
                observations.append(error_msg)
    
    # Create tool message outputs
    tool_outputs = [
        ToolMessage(
            content=str(observation),
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        )
        for observation, tool_call in zip(observations, tool_calls)
    ]
    
    return {
        "messages": tool_outputs,
        "tool_iteration_count": new_count,
    }


def finalize_output(state: AgentState) -> AgentState:
    """Use LLM to construct final summary and status based on agent's work."""
    result = _model_finalize.invoke([SystemMessage(content=FINALIZE_OUTPUT_PROMPT)] + state["messages"])
    
    return {
        "agent_summary": result.agent_summary,
        "status": result.status,
    }


def routing_after_agent_decision(state: AgentState) -> Literal["tools", "finalize"]:
    """After agent LLM, route to tools if it made tool calls, otherwise finalize."""
    messages = state["messages"]
    
    # Find the last AIMessage (skip pre_reasoning if it's the last)
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg
            break
    
    # Check max iterations before allowing more tool calls
    current_count = state["tool_iteration_count"]
    if current_count >= settings.max_tool_iterations:
        print(f"⛔ Max tool iterations ({settings.max_tool_iterations}) reached, forcing exit")
        return "finalize"
    
    if last_ai_msg and last_ai_msg.tool_calls:
        print(f"➡️  Routing to tools node (iteration {current_count + 1}/{settings.max_tool_iterations})")
        return "tools"
    
    # Otherwise, we have a final answer
    print(f"➡️  Routing to finalize (no tool calls)")
    return "finalize"


def routing_after_classify(state: AgentState) -> Literal["generate_plan", "reject"]:
    """After classification, route to planning or rejection."""
    if state["is_profiling"]:
        print(f"➡️  Routing to generate_plan (profiling query)")
        return "generate_plan"
    print(f"➡️  Routing to reject (non-profiling query)")
    return "reject"


def routing_after_plan_analysis(state: AgentState) -> Literal["agent", "__end__"]:
    """After plan analysis, route based on tools_missing boolean."""
    if state.get("tools_missing") is True:
        print(f"➡️  Routing to END (missing tools detected)")
        return "__end__"
    print(f"➡️  Routing to agent (all tools available)")
    return "agent"


def create_agent_executor():
    """Create a LangGraph executor with query classification and tool loop only."""
    graph = StateGraph(AgentState, output_schema=AgentOutputState)
    
    # Nodes
    graph.add_node("system_prompt", add_system_message)
    graph.add_node("classify_query", classify_query)
    graph.add_node("generate_plan", generate_plan)
    graph.add_node("analyze_plan", analyze_plan)
    graph.add_node("agent", agent_llm)
    graph.add_node("tools", tool_node)
    graph.add_node("reject", send_rejection)
    graph.add_node("finalize", finalize_output)
    
    # Edges
    graph.add_edge(START, "system_prompt")
    graph.add_edge("system_prompt", "classify_query")
    graph.add_conditional_edges(
        "classify_query",
        routing_after_classify,
        {
            "generate_plan": "generate_plan",
            "reject": "reject"
        }
    )
    graph.add_edge("generate_plan", "analyze_plan")
    graph.add_conditional_edges(
        "analyze_plan",
        routing_after_plan_analysis,
        {
            "agent": "agent",
            "__end__": END,
        }
    )
    graph.add_conditional_edges(
        "agent",
        routing_after_agent_decision,
        {
            "tools": "tools",
            "finalize": "finalize",
        },
    )
    graph.add_edge("tools", "agent")    
    graph.add_edge("finalize", END)
    graph.add_edge("reject", END)
    
    compiled = graph.compile()
    return compiled
