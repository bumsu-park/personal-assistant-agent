from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from langgraph.graph import END, StateGraph

from src.core.llm import create_llm
from src.core.memory import get_checkpointer
from src.core.nodes import create_nodes
from src.core.plugin import Plugin
from src.core.state import AgentState

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)


async def create_agent(
    plugins: list[Plugin],
    config: Config,
    system_prompt_builder: Callable[[], str] | None = None,
    checkpointer=None,
):
    """Build and compile a LangGraph agent from the given plugins."""
    for p in plugins:
        await p.setup()

    all_tools = []
    for p in plugins:
        all_tools.extend(p.tools())

    if system_prompt_builder is None:
        system_prompt_builder = config.build_system_prompt

    llm = create_llm(config)
    agent_node, tool_node = create_nodes(all_tools, llm, system_prompt_builder, config)

    def should_continue(state: AgentState) -> str:
        return state["next_action"]

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")

    if checkpointer is None:
        checkpointer = await get_checkpointer(config)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Agent graph created for %s.", config.agent_name)
    return compiled
