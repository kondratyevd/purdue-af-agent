from tools import TOOL_LIST


# Classification prompt (used in classify_query node)
CLASSIFICATION_PROMPT = (
    "Determine if the user's message is about profiling, performance analysis, "
    "CPU/memory usage, or similar performance-related topics."
)


# Agent node prompts
GLOBAL_SYSTEM_PROMPT = (
    "You are a profiling assistant. Extract time ranges and metadata from user queries. "
    "Do NOT retrieve profiling data (CPU, memory, etc.) - that functionality is not implemented. "
    "Focus on extracting time windows and user information. Keep responses concise and accurate."
)

METADATA_EXTRACTION_PROMPT = f"""Extract start_time and end_time in ISO 8601 format, and username from the user's message.

AVAILABLE TOOLS:
{TOOL_LIST}

INSTRUCTIONS:
- Absolute times (e.g., "2024-01-15 14:00"): Construct ISO 8601 directly without tools
- Relative times (e.g., "last Tuesday", "yesterday", "1 hour ago"): Use tools - get current time first
- Use tools for parsing ambiguous formats, timezone conversions, or date calculations
- CRITICAL: Only use tools listed above. Use EXACT parameter names from tool signatures
- Continue until both start_time and end_time are extracted in ISO 8601, or determined unavailable
- Extract username from user's message
- Return None for any field if not found"""


# Think node prompt
THINK_REFLECTION_PROMPT_TEMPLATE = """You executed '{tool_name}' and received:

{tool_result}

Available tools: {available_tools}

Provide exactly 2 sentences:
1. What has been done so far (information gathered)
2. Next step (specific tool to call, or provide final answer)"""


# Finalize node prompt
FINALIZE_OUTPUT_PROMPT = (
    "Review the conversation and generate a SINGLE PARAGRAPH summary of what was accomplished and the final result. "
    "Write one continuous paragraph - no bullets, sections, or line breaks.\n\n"
    "**CRITICAL: Use ONLY the final extracted values below for dates/times. "
    "Do NOT reference intermediate or incorrect dates from the conversation.**"
)
