from langchain_core.messages import AIMessage, SystemMessage
from langchain.chat_models import init_chat_model
from tools import TOOLS_BY_NAME
from schemas import ToolCallsExtraction
from config import settings

# Initialize model for tool call extraction (reused across calls)
_model_extractor = None


def _get_extractor():
    """Get or initialize the LLM extractor for tool calls."""
    global _model_extractor
    if _model_extractor is None:
        model = init_chat_model(
            model=settings.openai_model,
            model_provider="openai",
            temperature=0,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key or None,
        )
        _model_extractor = model.with_structured_output(ToolCallsExtraction)
    return _model_extractor


def validate_and_fix_tool_calls(ai_msg: AIMessage) -> AIMessage:
    """Intercept AIMessage and use LLM to extract/convert tool calls to proper LangChain format."""
    # Use LLM to extract and convert tool calls
    extractor = _get_extractor()
    available_tools = list(TOOLS_BY_NAME.keys())

    prompt = f"""Analyze the AI message and extract any tool/function calls in any format.

The message may contain tool calls in:
- tool_calls attribute (LangChain format)
- JSON in content
- OpenAI function calling format
- Other formats

Convert ALL tool calls to LangChain format: {{"name": "tool_name", "args": {{...}}, "id": "unique_id"}}

Available tools: {', '.join(available_tools)}

Extract and format all tool calls. Return empty list if none found."""

    try:
        result = extractor.invoke([SystemMessage(content=prompt), ai_msg])
        tool_calls = []
        for tc in result.tool_calls:
            # Validate tool exists
            if tc.name in TOOLS_BY_NAME:
                tool_calls.append(
                    {
                        "name": tc.name,
                        "args": tc.args,
                        "id": tc.id,
                    }
                )
            else:
                print(f"  ⚠️  LLM extracted unknown tool: {tc.name}")

        # Create updated AIMessage with extracted tool calls
        return AIMessage(
            content=ai_msg.content,
            tool_calls=tool_calls if tool_calls else None,
        )
    except Exception as e:
        print(f"  ✗ LLM extraction failed: {e}, returning original message")
        return ai_msg
