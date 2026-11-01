"""
Chatbot Service

Orchestrates the interaction between the user, the Gemini API, and the MCP server.

For each chat message:
1. Look up the user's session-isolated DuckDB database
2. Start an MCP server connected to that database
3. Discover available MCP tools
4. Pass the user's question + tools to Gemini
5. Execute the function-calling loop (Gemini ↔ MCP)
6. Return the final natural-language answer
7. Shut down the MCP server (per-message lifecycle)
"""

import logging
from src.mcp_client import MCPClientManager
from src.gemini_integration import GeminiIntegration
from src.session_manager import get_session_data

logger = logging.getLogger(__name__)


class ChatbotService:
    """Manages chatbot interactions via Gemini + MCP."""

    def __init__(self):
        self.gemini = GeminiIntegration()

    async def process_chat_message(self, session_id: str, message: str) -> str:
        """
        Process a user's chat message against their session-isolated dataset.

        Args:
            session_id: The user's dataset session ID (from Flask session cookie)
            message: The user's natural-language question

        Returns:
            Natural-language answer from Gemini after querying the database.

        Raises:
            ValueError: If the session is not found or has no database.
        """
        # Look up the session's database path
        session_data = get_session_data(session_id)
        if not session_data:
            raise ValueError(f"Session not found: {session_id}")

        db_path = session_data['db_path']
        logger.info(f"Processing chat message for session {session_id}: {message[:60]}...")

        # Start the MCP server for this database
        mcp_client = MCPClientManager(db_path)

        try:
            await mcp_client.start_mcp_server()

            # Discover available tools
            tools = await mcp_client.discover_tools()

            # Execute the Gemini function-calling loop
            answer = await self.gemini.chat_with_tools(
                message=message,
                mcp_tools=tools,
                mcp_client=mcp_client,
                max_iterations=5
            )

            logger.info(f"Chat response generated for session {session_id}")
            return answer

        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            raise

        finally:
            # Always clean up the MCP server subprocess
            await mcp_client.close()
