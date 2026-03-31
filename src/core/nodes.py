from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain_core.messages import SystemMessage, ToolMessage

from src.core.state import AgentState

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)


def create_nodes(
    tools: list,
    llm,
    system_prompt_builder: Callable[[], str],
    config: Config,
):
    """Returns (agent_node, tool_node) closures bound to the given tools/llm."""
    tools_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: AgentState) -> dict:
        logger.info(f"Agent Node - user: {state['user_id']}")
        system_msg = SystemMessage(content=system_prompt_builder())

        history = list(state["messages"])
        if history and isinstance(history[0], SystemMessage):
            history[0] = system_msg
        else:
            history.insert(0, system_msg)

        max_msgs = config.MAX_MESSAGES
        if len(history) > max_msgs:
            history = [history[0], *history[-(max_msgs - 1):]]

        response = await llm_with_tools.ainvoke(history)

        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(f"LLM requested {len(response.tool_calls)} tool calls")
            next_action = "tools"
        else:
            logger.info("No tool calls necessary")
            next_action = "end"

        return {"messages": [response], "next_action": next_action}

    async def tool_node(state: AgentState) -> dict:
        logger.info(f"Tool Node - user: {state['user_id']}")
        last_message = state["messages"][-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            logger.warning("Tool node called but no tool calls found")
            return {"next_action": "end"}

        tool_messages = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            tool = tools_map.get(tool_name)

            if tool:
                try:
                    try:
                        result = await tool.ainvoke(tool_args)
                    except NotImplementedError:
                        result = tool.invoke(tool_args)
                    tool_messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_id)
                    )
                    logger.info(f"Tool {tool_name} executed successfully")
                except Exception as e:
                    logger.error(
                        f"Error executing tool {tool_name}: {e}", exc_info=True
                    )
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error: {e!s}", tool_call_id=tool_id
                        )
                    )
            else:
                logger.error(f"Unknown tool: {tool_name}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Unknown tool: {tool_name}", tool_call_id=tool_id
                    )
                )

        return {"messages": tool_messages, "next_action": "agent"}

    return agent_node, tool_node
