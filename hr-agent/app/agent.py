"""LangChain agent implementation using LLM (OpenAI/Claude) and MCP tools."""
import logging
from typing import List, Dict, Any
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.config import settings
from app.auth import TokenContext
from app.mcp_client import MCPClient
from app.tools import MCPToolFactory

logger = logging.getLogger(__name__)


class HRAgent:
    """HR Agent using LangChain, Claude, and MCP tools."""

    def __init__(self, token_context: TokenContext):
        """
        Initialize HR Agent.

        Args:
            token_context: Token context with user scopes and auth headers
        """
        self.token_context = token_context
        self.mcp_client = MCPClient()

    def _create_system_prompt(self) -> str:
        """
        Create system prompt including user's available scopes.

        Returns:
            System prompt string
        """
        scopes_text = ", ".join(self.token_context.scopes_list) if self.token_context.scopes_list else "none"

        return f"""You are an HR Assistant with access to employee data and HR systems.

**Authorization Context:**
- User: {self.token_context.user_sub or 'Unknown'}
- Granted Scopes: {scopes_text}
- Authorization is enforced by Kong Gateway at each API boundary

**Your Capabilities:**
You have access to HR tools that allow you to:
- View employee information
- Update employee records
- List departments
- View salary information
- Update salary information
- View organizational chart

**IMPORTANT - Tool Selection for Efficiency:**
To avoid exceeding iteration limits, ALWAYS prefer these efficient tools:

1. **For salary queries** (finding highest/lowest, listing salaries, comparing compensation):
   - ✅ USE: `list_employees_with_salaries` (gets ALL employees with salaries in ONE call)
   - ❌ AVOID: Calling `get_salary` multiple times for each employee

2. **For department-based queries** (employees per department, department organization):
   - ✅ USE: `list_employees_by_department` (gets employees grouped by department in ONE call)
   - ❌ AVOID: Filtering employees manually or calling `get_employee` multiple times

3. **For simple employee lists** (names, IDs only):
   - ✅ USE: `list_employees` (lightweight, fast)

**Guidelines:**
1. Always be helpful and professional
2. Choose the MOST EFFICIENT tool for each query
3. If a tool call fails, report the error message to the user
4. Provide clear, concise answers
5. Respect data sensitivity - salary information is particularly sensitive

Note: Access control is handled by Kong Gateway. If you encounter authorization errors when calling tools, inform the user that they lack the necessary permissions.
"""

    async def create_agent_executor(self) -> AgentExecutor:
        """
        Create LangChain agent executor with LLM and MCP tools.

        Returns:
            Configured AgentExecutor
        """
        # Initialize LLM - Kong AI Proxy handles API key and provider routing
        # We send model="gpt-4" to match Kong's configuration (not to override it)
        # Note: Kong's AI Proxy configuration controls max_tokens, not set here to avoid conflicts
        llm = ChatOpenAI(
            model="gpt-4",  # Must match Kong AI Proxy configuration
            api_key="placeholder",  # Required by library, Kong overrides with real API key
            base_url=settings.llm_api_url,
            default_headers=self.token_context.get_headers(),  # Send auth for Kong validation
        )

        # Get available tools based on user scopes
        tool_factory = MCPToolFactory(self.mcp_client, self.token_context)
        tools = await tool_factory.get_available_tools()

        logger.info(f"Agent initialized with {len(tools)} tools: {[t.name for t in tools]}")

        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._create_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create agent
        agent = create_tool_calling_agent(llm, tools, prompt)

        # Create agent executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=20,  # Increased from 10 to handle queries requiring multiple tool calls
        )

        return agent_executor

    async def chat(self, message: str, chat_history: List[Dict[str, str]] = None) -> str:
        """
        Process a chat message.

        Args:
            message: User message
            chat_history: Optional chat history

        Returns:
            Agent response
        """
        try:
            agent_executor = await self.create_agent_executor()

            # Prepare input
            agent_input = {
                "input": message,
                "chat_history": chat_history or [],
            }

            # Execute agent
            logger.info(f"Processing message: {message}")
            result = await agent_executor.ainvoke(agent_input)

            response = result.get("output", "I apologize, but I couldn't generate a response.")
            logger.info(f"Agent response generated successfully")

            return response

        except Exception as e:
            error_msg = f"Error processing chat: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"I encountered an error: {str(e)}"
