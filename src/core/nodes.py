import logging
from typing import Callable
from src.core.state import AgentState
from src.core.config import Config
from langchain_core.messages import SystemMessage, ToolMessage

logger = logging.getLogger(__name__)


def create_nodes(
    tools: list,
    llm,
    system_prompt_builder: Callable[[], str],
):
    """Returns (agent_node, tool_node) closures bound to the given tools/llm."""
    tools_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: AgentState) -> AgentState:
        logger.info(f"Agent Node - user: {state.user_id}")
        system_msg = SystemMessage(content=system_prompt_builder())

        if state.messages and isinstance(state.messages[0], SystemMessage):
            state.messages[0] = system_msg
        else:
            state.messages.insert(0, system_msg)

        max_msgs = Config.MAX_MESSAGES
        if len(state.messages) > max_msgs:
            state.messages = [state.messages[0]] + state.messages[-(max_msgs - 1) :]

        response = await llm_with_tools.ainvoke(state.messages)
        state.messages.append(response)

        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(f"LLM requested {len(response.tool_calls)} tool calls")
            state.next_action = "tools"
        else:
            logger.info("No tool calls necessary")
            state.next_action = "end"

        return state

    async def tool_node(state: AgentState) -> AgentState:
        logger.info(f"Tool Node - user: {state.user_id}")
        last_message = state.messages[-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            logger.warning("Tool node called but no tool calls found")
            state.next_action = "end"
            return state

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
                            content=f"Error: {str(e)}", tool_call_id=tool_id
                        )
                    )
            else:
                logger.error(f"Unknown tool: {tool_name}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Unknown tool: {tool_name}", tool_call_id=tool_id
                    )
                )

        state.messages.extend(tool_messages)
        state.next_action = "agent"

        return state

    return agent_node, tool_node
