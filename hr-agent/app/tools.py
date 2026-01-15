"""LangChain tool wrappers for MCP tools."""
import logging
from typing import Any, Dict, List, Optional
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from app.mcp_client import MCPClient
from app.auth import TokenContext

logger = logging.getLogger(__name__)


# Pydantic models for tool arguments
class GetEmployeeArgs(BaseModel):
    employee_id: str = Field(description="The employee ID (e.g., emp-001)")


class UpdateEmployeeArgs(BaseModel):
    employee_id: str = Field(description="The employee ID")
    title: Optional[str] = Field(None, description="New job title")
    location: Optional[str] = Field(None, description="New location")


class ListDepartmentsArgs(BaseModel):
    """No arguments required for list_departments."""
    pass


class GetSalaryArgs(BaseModel):
    employee_id: str = Field(description="The employee ID")


class UpdateSalaryArgs(BaseModel):
    employee_id: str = Field(description="The employee ID")
    base: Optional[int] = Field(None, description="New base salary")
    bonus: Optional[int] = Field(None, description="New bonus amount")


class GetOrgChartArgs(BaseModel):
    """No arguments required for get_org_chart."""
    pass


class ListEmployeesArgs(BaseModel):
    """No arguments required for list_employees."""
    pass


class ListEmployeesWithSalariesArgs(BaseModel):
    """No arguments required for list_employees_with_salaries."""
    pass


class ListEmployeesByDepartmentArgs(BaseModel):
    """No arguments required for list_employees_by_department."""
    pass


class MCPToolFactory:
    """Factory for creating LangChain tools from MCP tools."""

    def __init__(self, mcp_client: MCPClient, token_context: TokenContext):
        """
        Initialize tool factory.

        Args:
            mcp_client: MCP client instance
            token_context: Token context with user scopes and headers
        """
        self.mcp_client = mcp_client
        self.token_context = token_context
        self.headers = token_context.get_headers()

    async def get_available_tools(self) -> List[StructuredTool]:
        """
        Get list of available LangChain tools.

        NOTE: Scope enforcement temporarily disabled - all tools available.
        Kong ACL will handle scope verification at the MCP gateway level.

        Returns:
            List of LangChain StructuredTool instances
        """
        # Query MCP server for all tools WITHOUT scope filtering
        # We still send auth headers for token exchange, but MCP server should return all tools
        # Kong ACL will enforce scopes when tools are actually called
        mcp_tools = await self.mcp_client.list_tools(headers=self.headers)

        logger.info(f"Available MCP tools (scope checking disabled, Kong will enforce): {[t['name'] for t in mcp_tools]}")

        # Map MCP tools to LangChain tools
        langchain_tools = []
        for mcp_tool in mcp_tools:
            tool_name = mcp_tool["name"]
            tool = self._create_langchain_tool(tool_name, mcp_tool)
            if tool:
                langchain_tools.append(tool)

        return langchain_tools

    def _create_langchain_tool(
        self, tool_name: str, mcp_tool: Dict[str, Any]
    ) -> Optional[StructuredTool]:
        """
        Create a LangChain StructuredTool from an MCP tool definition.

        Args:
            tool_name: Name of the tool
            mcp_tool: MCP tool definition

        Returns:
            StructuredTool instance or None
        """
        description = mcp_tool.get("description", "")

        # Define tool-specific handlers
        if tool_name == "get_employee":
            return StructuredTool(
                name="get_employee",
                description=description,
                func=self._make_tool_func("get_employee"),
                coroutine=self._make_tool_coroutine("get_employee"),
                args_schema=GetEmployeeArgs,
            )
        elif tool_name == "update_employee":
            return StructuredTool(
                name="update_employee",
                description=description,
                func=self._make_tool_func("update_employee"),
                coroutine=self._make_tool_coroutine("update_employee"),
                args_schema=UpdateEmployeeArgs,
            )
        elif tool_name == "list_departments":
            return StructuredTool(
                name="list_departments",
                description=description,
                func=self._make_tool_func("list_departments"),
                coroutine=self._make_tool_coroutine("list_departments"),
                args_schema=ListDepartmentsArgs,
            )
        elif tool_name == "get_salary":
            return StructuredTool(
                name="get_salary",
                description=description,
                func=self._make_tool_func("get_salary"),
                coroutine=self._make_tool_coroutine("get_salary"),
                args_schema=GetSalaryArgs,
            )
        elif tool_name == "update_salary":
            return StructuredTool(
                name="update_salary",
                description=description,
                func=self._make_tool_func("update_salary"),
                coroutine=self._make_tool_coroutine("update_salary"),
                args_schema=UpdateSalaryArgs,
            )
        elif tool_name == "get_org_chart":
            return StructuredTool(
                name="get_org_chart",
                description=description,
                func=self._make_tool_func("get_org_chart"),
                coroutine=self._make_tool_coroutine("get_org_chart"),
                args_schema=GetOrgChartArgs,
            )
        elif tool_name == "list_employees":
            return StructuredTool(
                name="list_employees",
                description=description,
                func=self._make_tool_func("list_employees"),
                coroutine=self._make_tool_coroutine("list_employees"),
                args_schema=ListEmployeesArgs,
            )
        elif tool_name == "list_employees_with_salaries":
            return StructuredTool(
                name="list_employees_with_salaries",
                description=description,
                func=self._make_tool_func("list_employees_with_salaries"),
                coroutine=self._make_tool_coroutine("list_employees_with_salaries"),
                args_schema=ListEmployeesWithSalariesArgs,
            )
        elif tool_name == "list_employees_by_department":
            return StructuredTool(
                name="list_employees_by_department",
                description=description,
                func=self._make_tool_func("list_employees_by_department"),
                coroutine=self._make_tool_coroutine("list_employees_by_department"),
                args_schema=ListEmployeesByDepartmentArgs,
            )

        logger.warning(f"Unknown MCP tool: {tool_name}")
        return None

    def _make_tool_func(self, tool_name: str):
        """Create a synchronous wrapper function (required by LangChain)."""
        def sync_wrapper(**kwargs):
            raise NotImplementedError(
                f"Use async version of {tool_name} - sync calls not supported"
            )
        return sync_wrapper

    def _make_tool_coroutine(self, tool_name: str):
        """Create an async wrapper function for calling MCP tools."""
        async def async_wrapper(**kwargs):
            try:
                logger.info(f"Executing tool {tool_name} with args: {kwargs}")
                result = await self.mcp_client.call_tool(
                    tool_name=tool_name,
                    arguments=kwargs,
                    headers=self.headers,
                )
                logger.info(f"Tool {tool_name} completed successfully")
                return result
            except Exception as e:
                error_msg = f"Error calling {tool_name}: {str(e)}"
                logger.error(error_msg)
                return f"ERROR: {error_msg}"

        return async_wrapper
