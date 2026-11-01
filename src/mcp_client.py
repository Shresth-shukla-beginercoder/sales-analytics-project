"""
MCP Client Manager

Spawns and manages a connection to the MotherDuck MCP server (mcp-server-motherduck).
The server exposes DuckDB via MCP tools: execute_query, list_databases, list_tables, list_columns.

The server runs in READ-ONLY mode by default (write access requires --read-write flag, which
we never pass). Each session gets its own server process tied to one DuckDB file.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. Chatbot will not function until 'pip install mcp' succeeds.")


class MCPClientManager:
    """Manages an MCP server process for a single DuckDB database."""

    def __init__(self, db_path: str):
        if not MCP_AVAILABLE:
            raise ImportError("MCP SDK is not installed. Run: pip install mcp mcp-server-motherduck")

        self.db_path = db_path
        self.session: Optional[ClientSession] = None
        self.read = None
        self.write = None
        self._exit_stack = None

    async def start_mcp_server(self):
        """
        Start the MCP server subprocess and initialize the session.

        The server launches in READ-ONLY mode (default for mcp-server-motherduck).
        Uses async context managers to ensure subprocess cleanup.
        """
        try:
            from contextlib import AsyncExitStack

            # The absolute path is required; mcp-server-motherduck rejects :memory: or relative paths in production
            abs_db_path = os.path.abspath(self.db_path)

            server_params = StdioServerParameters(
                command="mcp-server-motherduck",
                args=[
                    "--db-path", abs_db_path,
                    # READ-ONLY is the default (no --read-write flag)
                    "--max-rows", "10000",
                    "--query-timeout", "30"
                ],
                env={**os.environ}
            )

            # Use AsyncExitStack to properly manage the stdio_client context
            self._exit_stack = AsyncExitStack()
            self.read, self.write = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )

            self.session = ClientSession(self.read, self.write)
            await self._exit_stack.enter_async_context(self.session)
            await self.session.initialize()

            logger.info(f"MCP server started for database: {abs_db_path}")

        except Exception as e:
            logger.error(f"Failed to start MCP server: {str(e)}")
            if self._exit_stack:
                await self._exit_stack.aclose()
            raise

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Discover available MCP tools from the server.

        MotherDuck server exposes:
        - execute_query (sql: str) → query results
        - list_databases ()
        - list_tables (database?: str, schema?: str)
        - list_columns (table: str, database?: str, schema?: str)

        Returns:
            List of tool schemas suitable for Gemini function declarations.
        """
        if not self.session:
            raise RuntimeError("MCP server not started. Call start_mcp_server() first.")

        try:
            response = await self.session.list_tools()
            tools = []

            for tool in response.tools:
                tools.append({
                    'name': tool.name,
                    'description': tool.description or f"MCP tool: {tool.name}",
                    'parameters': tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                })

            logger.info(f"Discovered {len(tools)} MCP tools: {[t['name'] for t in tools]}")
            return tools

        except Exception as e:
            logger.error(f"Error discovering MCP tools: {str(e)}")
            raise

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute an MCP tool with the given arguments.

        Args:
            tool_name: Name of the tool (e.g., 'execute_query')
            arguments: Tool arguments (e.g., {'sql': 'SELECT * FROM sales LIMIT 10'})

        Returns:
            Tool execution result (structure depends on the tool).
        """
        if not self.session:
            raise RuntimeError("MCP server not started. Call start_mcp_server() first.")

        try:
            result = await self.session.call_tool(tool_name, arguments)
            logger.debug(f"MCP tool '{tool_name}' executed successfully")
            return result

        except Exception as e:
            logger.error(f"Error calling MCP tool '{tool_name}': {str(e)}")
            raise

    async def close(self):
        """
        Shut down the MCP server and clean up resources.

        Properly closes the subprocess via the AsyncExitStack context managers.
        """
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
                logger.info("MCP server closed")
            except Exception as e:
                logger.error(f"Error closing MCP server: {str(e)}")
            finally:
                self.session = None
                self.read = None
                self.write = None
                self._exit_stack = None
