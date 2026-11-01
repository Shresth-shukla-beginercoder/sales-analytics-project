"""
Gemini Integration

Handles communication with Google's Gemini API, including:
- Converting MCP tools to Gemini function declarations
- Executing the function-calling loop (detect function calls, invoke MCP tools, return results)
- Returning natural-language answers to the user

The integration uses the official google-genai SDK and reads the API key from
the GEMINI_API_KEY environment variable only.
"""

import logging
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# HTTP status codes that indicate a transient, retryable Gemini failure
# (load spikes / throttling / brief outages). A 503 "high demand" spike is
# temporary, so we retry with backoff instead of surfacing a hard 500.
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def _is_transient_error(exc: Exception) -> bool:
    """True if the exception is a retryable Gemini/HTTP transient failure."""
    code = getattr(exc, 'code', None)
    if code in _TRANSIENT_STATUS:
        return True
    text = str(exc).lower()
    return any(marker in text for marker in ('503', '429', 'high demand', 'unavailable', 'rate limit', 'quota exceeded temporarily'))

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai SDK not installed. Chatbot will not function until 'pip install google-genai' succeeds.")


# Keys from an MCP JSON-Schema that Gemini's function-calling API accepts
# inside a FunctionDeclaration. MCP servers (e.g. MotherDuck) add extras like
# 'additionalProperties', which the API rejects as unknown fields, so only the
# core JSON-Schema subset is passed through. Nested properties are converted to
# explicit types.Schema objects (see _to_gemini_schema).
_SCHEMA_KEYS = {
    'type', 'description', 'properties', 'required', 'items', 'enum',
}


def _to_gemini_schema(d: Dict[str, Any]) -> Any:
    """Recursively build nested types.Schema objects from an MCP JSON-Schema dict."""
    clean = {k: v for k, v in d.items() if k in _SCHEMA_KEYS}
    if 'properties' in clean and isinstance(clean['properties'], dict):
        clean['properties'] = {
            name: _to_gemini_schema(val) if isinstance(val, dict) else val
            for name, val in clean['properties'].items()
        }
    if isinstance(clean.get('items'), dict):
        clean['items'] = _to_gemini_schema(clean['items'])
    # Only keep required properties that are actually defined
    if clean.get('required'):
        clean['required'] = [
            r for r in clean['required']
            if r in (clean.get('properties') or {})
        ]
    return types.Schema(**clean) if clean else None


def _build_gemini_schema(parameters: Dict[str, Any]) -> Optional[Any]:
    """
    Convert an MCP JSON-Schema dict into a google-genai Schema object.

    FunctionDeclaration.parameters must be a types.Schema, not a plain dict.
    Only the core JSON-Schema subset is passed through (recursively, so nested
    property schemas become Schema objects too); everything else is dropped.
    """
    if not parameters:
        return None
    return _to_gemini_schema(parameters)


def convert_mcp_tools_to_gemini_functions(mcp_tools: List[Dict[str, Any]]) -> List[Any]:
    """
    Convert MCP tool schemas to Gemini FunctionDeclaration format.

    Args:
        mcp_tools: List of tool schemas from MCP server (name, description, parameters)

    Returns:
        List of FunctionDeclaration objects for Gemini's Tool constructor.
    """
    if not GEMINI_AVAILABLE:
        raise ImportError("google-genai SDK is not installed")

    function_declarations = []

    for tool in mcp_tools:
        # Convert MCP JSON Schema parameters to Gemini's Schema format
        parameters = tool.get('parameters') or {}
        schema = _build_gemini_schema(parameters)

        func_decl = types.FunctionDeclaration(
            name=tool['name'],
            description=tool['description'],
            parameters=schema
        )

        function_declarations.append(func_decl)

    logger.debug(f"Converted {len(function_declarations)} MCP tools to Gemini functions")
    return function_declarations


class GeminiIntegration:
    """Manages Gemini API interactions with function-calling support."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 model_fallbacks: Optional[List[str]] = None):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (reads from GEMINI_API_KEY env var if None)
            model: Primary model identifier (reads GEMINI_MODEL env var if None)
            model_fallbacks: Ordered fallback models, tried when the primary is
                unavailable or under load (reads GEMINI_MODEL_FALLBACKS if None)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-genai SDK is not installed. Run: pip install google-genai")

        from config.settings import Config

        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model = model or Config.GEMINI_MODEL
        self.model_fallbacks = model_fallbacks if model_fallbacks is not None else list(Config.GEMINI_MODEL_FALLBACKS)
        self._last_good_model = None  # remembers which model last answered OK

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"Gemini client initialized with model: {self.model} "
                    f"(fallbacks: {self.model_fallbacks})")

    def _model_chain(self) -> List[str]:
        """Ordered model list to try: last-known-good first, then primary, then fallbacks."""
        chain = [self.model] + [m for m in self.model_fallbacks if m and m != self.model]
        if self._last_good_model and self._last_good_model in chain:
            chain.remove(self._last_good_model)
            chain.insert(0, self._last_good_model)
        return chain

    @staticmethod
    def _is_model_unavailable(exc: Exception) -> bool:
        """True when the error means 'this model won't work right now' (fall back to next)."""
        code = getattr(exc, 'code', None)
        if code == 404:
            return True
        text = str(exc).lower()
        if any(marker in text for marker in ('no longer available', 'is not found', 'is not supported')):
            return True
        # A transient error that survived the internal retry backoff also
        # means "try the next model" (another model may have capacity).
        return _is_transient_error(exc)

    def _generate_with_retry(self, max_retries: int = 4, **kwargs):
        """
        Call generate_content with retry + backoff for transient errors.

        The Gemini API can return 503 "high demand" or 429 throttling under
        load. Rather than failing the whole chat message, retry with
        exponential backoff (1s, 2s, 4s, 8s) up to max_retries times.
        Non-transient errors (4xx, 400, 401, 404) are raised immediately.
        """
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                return self.client.models.generate_content(**kwargs)
            except Exception as e:
                if not _is_transient_error(e):
                    raise
                last_exc = e
                if attempt == max_retries:
                    break
                wait = min(2 ** attempt, 8)
                logger.warning(
                    f"Gemini transient error ({str(e)[:100]}), "
                    f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
        # Exhausted retries on a transient error
        raise last_exc


    async def chat_with_tools(
        self,
        message: str,
        mcp_tools: List[Dict[str, Any]],
        mcp_client,
        max_iterations: int = 5
    ) -> str:
        """
        Execute a chat query with function-calling support.

        This implements the full Gemini↔MCP function-calling loop:
        1. Send user message + available tools to Gemini
        2. If Gemini returns a function call, execute it via MCP
        3. Send the function result back to Gemini
        4. Repeat until Gemini returns a text response (up to max_iterations)

        Args:
            message: User's natural-language question
            mcp_tools: List of MCP tool schemas
            mcp_client: MCPClientManager instance (for calling tools)
            max_iterations: Maximum function-call rounds (prevents infinite loops)

        Returns:
            Final natural-language answer from Gemini.

        Any model in the chain can serve the request: the primary model is tried
        first (or the last one that actually worked), then GEMINI_MODEL_FALLBACKS
        in order, until one answers.
        """
        last_error: Optional[Exception] = None
        for model in self._model_chain():
            try:
                return await self._run_chat_loop(
                    model=model, message=message, mcp_tools=mcp_tools,
                    mcp_client=mcp_client, max_iterations=max_iterations
                )
            except Exception as e:
                if self._is_model_unavailable(e):
                    logger.warning(
                        f"Gemini model '{model}' unavailable ({str(e)[:120]}); "
                        f"trying next fallback..."
                    )
                    last_error = e
                    continue
                raise
        if last_error is not None:
            raise RuntimeError(f"All Gemini models in the chain failed. Last error: {last_error}")
        raise RuntimeError("No Gemini models configured (GEMINI_MODEL / GEMINI_MODEL_FALLBACKS)")

    async def _run_chat_loop(
        self,
        model: str,
        message: str,
        mcp_tools: List[Dict[str, Any]],
        mcp_client,
        max_iterations: int = 5
    ) -> str:
        """Run the full function-calling loop against one specific model."""
        try:
            # Convert MCP tools to Gemini function declarations
            function_declarations = convert_mcp_tools_to_gemini_functions(mcp_tools)

            if not function_declarations:
                logger.warning("No MCP tools available — responding without function-calling")
                response = self._generate_with_retry(
                    max_retries=3, model=model, contents=message
                )
                self._last_good_model = model
                return response.text

            # Build the Tool object
            tools = types.Tool(function_declarations=function_declarations)

            # System instruction for the Sales Analytics Assistant
            system_instruction = """You are a Sales Analytics Assistant. You help users analyze their sales data by querying a DuckDB database.

Available data columns typically include: product, quantity, price, sales, order_date, city, category, customer, region.

Rules:
1. NEVER invent or fabricate data — only report what the database returns.
2. Use the execute_query tool to run SQL SELECT queries against the 'sales' table.
3. When asked about totals, averages, or aggregations, write SQL with SUM(), AVG(), COUNT(), etc.
4. When asked for trends or time-series, GROUP BY order_date or use date functions.
5. Always verify column names with list_tables/list_columns before assuming they exist.
6. If a query returns no rows, tell the user "No data found" — do not make up results.
7. You can only read data (SELECT queries). You cannot INSERT, UPDATE, DELETE, or DROP.
8. Be concise but informative. Present numbers clearly.
9. If the user's question is unclear, ask for clarification instead of guessing.
10. Respond in plain, friendly text for a small chat box. NEVER use Markdown or special formatting: no **, no #, no bullet lists, no tables, no code blocks, no emojis.
11. Never add currency symbols (no $, no Rs, no rupee sign). Report the exact numbers the data returns, e.g. say "1741190" or "1,741,190"."""

            # Initialize conversation with the user message
            messages = [types.Content(
                role='user',
                parts=[types.Part(text=message)]
            )]

            # Function-calling loop
            for iteration in range(max_iterations):
                logger.debug(f"Function-calling iteration {iteration + 1}/{max_iterations}")

                response = self._generate_with_retry(
                    max_retries=3,
                    model=model,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=[tools],
                        temperature=0.3  # Lower temperature for more deterministic SQL generation
                    )
                )

                # Extract the candidate
                if not response.candidates or len(response.candidates) == 0:
                    logger.error("Gemini returned no candidates")
                    return "I am sorry, I could not process that request. Please try again."

                candidate = response.candidates[0]

                # Check if Gemini wants to call a function
                if candidate.content.parts and len(candidate.content.parts) > 0:
                    part = candidate.content.parts[0]

                    # If it's a function call, execute it
                    if hasattr(part, 'function_call') and part.function_call:
                        function_call = part.function_call
                        tool_name = function_call.name
                        tool_args = dict(function_call.args) if function_call.args else {}

                        logger.info(f"Gemini requested tool: {tool_name} with args: {tool_args}")

                        # Execute the MCP tool
                        try:
                            tool_result = await mcp_client.call_tool(tool_name, tool_args)

                            # Extract the actual content from the MCP result
                            # MCP returns a list of Content objects with text or other data
                            result_text = ""
                            if hasattr(tool_result, 'content') and tool_result.content:
                                for content_item in tool_result.content:
                                    if hasattr(content_item, 'text'):
                                        result_text += content_item.text
                                    elif hasattr(content_item, 'data'):
                                        result_text += str(content_item.data)
                            else:
                                result_text = str(tool_result)

                            logger.debug(f"Tool result: {result_text[:200]}...")

                            # Append the model's function call to history
                            messages.append(types.Content(
                                role='model',
                                parts=[part]
                            ))

                            # Append the function result
                            messages.append(types.Content(
                                role='user',
                                parts=[types.Part(
                                    function_response=types.FunctionResponse(
                                        name=tool_name,
                                        response={'result': result_text}
                                    )
                                )]
                            ))

                            # Continue the loop to get Gemini's natural-language response
                            continue

                        except Exception as e:
                            logger.error(f"Error executing MCP tool '{tool_name}': {str(e)}")

                            # Return the error to Gemini so it can explain it to the user
                            messages.append(types.Content(
                                role='model',
                                parts=[part]
                            ))
                            messages.append(types.Content(
                                role='user',
                                parts=[types.Part(
                                    function_response=types.FunctionResponse(
                                        name=tool_name,
                                        response={'error': str(e)}
                                    )
                                )]
                            ))
                            continue

                    # If it's a text response, return it
                    elif hasattr(part, 'text') and part.text:
                        self._last_good_model = model
                        return part.text

                # If we get here without a function call or text, something went wrong
                logger.warning(f"Unexpected response format at iteration {iteration + 1}")
                if hasattr(candidate, 'finish_reason'):
                    logger.warning(f"Finish reason: {candidate.finish_reason}")

                # Try to extract any text we can
                if hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            self._last_good_model = model
                            return part.text

                # If still nothing, break
                break

            # If we exhausted iterations without a final answer
            logger.warning(f"Function-calling loop reached max iterations ({max_iterations})")
            self._last_good_model = model
            return "I could not finish that analysis just now. Please try asking again, or split the question into smaller parts."

        except Exception as e:
            logger.error(f"Error in chat loop with model '{model}': {str(e)}")
            raise
