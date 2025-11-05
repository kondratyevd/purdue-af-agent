from tools import TOOL_LIST


GLOBAL_SYSTEM_PROMPT = (
    "You are a profiling assistant. Your task is to extract time ranges and metadata from user queries. "
    "You should NOT attempt to retrieve actual profiling data (CPU usage, memory, etc.) - that functionality is not yet implemented. "
    "Focus only on extracting time windows and user information. "
    "For absolute time references, construct ISO 8601 timestamps directly. "
    "Use tools only for relative times, parsing ambiguous formats, or timezone conversions. "
    "Keep responses concise and accurate."
)



PLANNING_PROMPT = f"""Create a concise, step-by-step plan to accomplish the user's request using ONLY the tools listed below.

AVAILABLE TOOLS:
{TOOL_LIST}

PLANNING GUIDELINES:
- Use tools only when necessary to obtain information, transform data, or perform deterministic operations that cannot be done reliably without a tool.
- Never invent or reference tools that are not in the available list.
- Minimize steps and tool calls while preserving correctness and clarity.
- For each step, specify:
  1) the exact tool name (or "no tool" if none is needed),
  2) what inputs/parameters will be required (names only, no example values),
  3) the purpose of the step and the expected outcome,
  4) how the result will be used by subsequent steps.

IMPORTANT:
- Do NOT include example argument values anywhere in the plan; only list parameter names.
- Keep the plan focused on actions and results; do not include code or pseudo-code.

Output a numbered list of steps that another agent could execute as-is using the listed tools."""


PLAN_ANALYSIS_PROMPT_TEMPLATE = f"""Analyze the following plan and determine whether the tools referenced are available.

AVAILABLE TOOLS:
{TOOL_LIST}

PLAN TO ANALYZE:
{{plan}}

EVALUATION GUIDELINES:
1. Extract tool names ONLY from steps that explicitly name a tool from the AVAILABLE TOOLS list above. Ignore:
   - Steps that describe actions without naming a tool
   - Steps labeled "no tool" or that say no tool is needed
   - Steps that describe direct calculations or data extraction (these don't need tools)
   - Steps that describe constructing timestamps directly (these don't need tools)
   - Narrative text or explanations
   - The phrase "no tool" itself (it is not a tool name)
2. Compare the extracted tool names against the AVAILABLE TOOLS list (exact name match).
3. If any explicitly named tool is NOT in the available list:
   - Respond with: "MISSING_TOOLS:" followed by a concise explanation listing the missing tool names and what each is expected to accomplish.
4. If all explicitly named tools are present in the available list (or there are no tool-using steps):
   - Respond with: "ALL_TOOLS_AVAILABLE".

CRITICAL: 
- "no tool" is NOT a tool name. 
- Steps that describe actions without explicitly naming a tool should be IGNORED - they don't require tools.
- Steps describing direct timestamp construction, text extraction, or calculations don't need tools.
- Only respond with MISSING_TOOLS if the plan explicitly names a tool that doesn't exist in the AVAILABLE TOOLS list.

Notes:
- Do not invent or assume tools beyond those explicitly named in the plan.
- Keep the analysis concise and action-oriented.
"""


METADATA_EXTRACTION_PROMPT = f"""Extract start_time and end_time from the user query in ISO 8601 format, and extract username from the user's message.

AVAILABLE TOOLS (use ONLY when needed for relative times, parsing, or conversions):
{TOOL_LIST}

INSTRUCTIONS:
- For absolute time references that can be directly converted to ISO 8601 without any context (e.g., "2024-01-15 14:00"), construct the timestamp directly without tools
- Use tools for any time reference that requires knowing the current date/time (e.g., "last Tuesday", "yesterday", "1 hour ago") - you MUST get the current time first using tools
- Use tools for relative time references, parsing ambiguous formats, timezone conversions, or calculations from reference points
- CRITICAL: You can ONLY use the tools listed above. Do not mention or attempt to use any other tools that are not in the list.
- Continue until you have extracted both start_time and end_time in ISO 8601 format, or determined they cannot be extracted from the query.
- When calling tools, include them in the tool_calls field with: name (exact tool name from the list above), args (dictionary with EXACT parameter names from tool signatures above), id (unique identifier)
- CRITICAL: Use the EXACT parameter names from the tool signatures above (e.g., use "time_str", "amount", "unit" for subtract_time_delta_tool, NOT "timestamp" or "delta")
- Prefer simpler, direct approaches - construct timestamps directly only when you have all the information needed without any context
- Extract username from the user's message and start_time/end_time in ISO 8601 format from the conversation
- Return None for any field if not found
-- If there's an APPROVED PLAN in the conversation, you MUST follow it step by step. The plan outlines the exact sequence of actions needed."""


FINALIZE_OUTPUT_PROMPT = (
    "Review your work from the conversation and generate a final summary and status.\n\n"
    "Generate a summary that summarizes what was accomplished and what the final result is.\n\n"
    "Set status to \"success\" if the task was completed successfully, otherwise \"partial\"."
)


