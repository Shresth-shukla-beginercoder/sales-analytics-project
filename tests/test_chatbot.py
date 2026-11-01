"""
Test suite for Chatbot Service functionality.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_process_chat_message():
    """Test chatbot message processing with mocked dependencies."""

    # Mock session data
    mock_session_data = {'db_path': 'test.db', 'created_at': None, 'active': True}

    # Mock MCP tool schema
    mock_tools = [
        {
            'name': 'execute_query',
            'description': 'Execute a SQL query',
            'parameters': {
                'type': 'object',
                'properties': {
                    'sql': {'type': 'string', 'description': 'SQL query'}
                },
                'required': ['sql']
            }
        }
    ]

    # Mock MCP tool result
    mock_tool_result = MagicMock()
    mock_tool_result.content = [MagicMock(text='{"total": 1000}')]

    with patch('src.chatbot_service.get_session_data', return_value=mock_session_data), \
         patch('src.chatbot_service.MCPClientManager') as mock_mcp_manager, \
         patch('src.chatbot_service.GeminiIntegration') as mock_gemini:

        # Setup MCP manager mock
        mock_mcp_instance = mock_mcp_manager.return_value
        mock_mcp_instance.start_mcp_server = AsyncMock()
        mock_mcp_instance.discover_tools = AsyncMock(return_value=mock_tools)
        mock_mcp_instance.call_tool = AsyncMock(return_value=mock_tool_result)
        mock_mcp_instance.close = AsyncMock()

        # Setup Gemini mock
        mock_gemini_instance = mock_gemini.return_value
        mock_gemini_instance.chat_with_tools = AsyncMock(return_value="The total sales is $1000.")

        # Import and test
        from src.chatbot_service import ChatbotService

        service = ChatbotService()
        answer = await service.process_chat_message('test_session', 'What is the total sales?')

        assert answer == "The total sales is $1000."
        mock_mcp_instance.start_mcp_server.assert_called_once()
        mock_mcp_instance.discover_tools.assert_called_once()
        mock_gemini_instance.chat_with_tools.assert_called_once()
        mock_mcp_instance.close.assert_called_once()


@pytest.mark.asyncio
async def test_process_chat_message_session_not_found():
    """Test chatbot behavior when session doesn't exist."""

    with patch('src.chatbot_service.get_session_data', return_value=None):
        from src.chatbot_service import ChatbotService

        service = ChatbotService()

        with pytest.raises(ValueError, match="Session not found"):
            await service.process_chat_message('invalid_session', 'Test question')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
