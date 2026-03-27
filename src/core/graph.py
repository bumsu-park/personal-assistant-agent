import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Optional
from langgraph.graph import StateGraph, END
from src.core.state import AgentState
from src.core.nodes import create_nodes
from src.core.llm import get_llm_service
from src.core.memory import get_checkpointer
from src.core.plugin import Plugin

logger = logging.getLogger(__name__)


async def create_agent(
    plugins: list[Plugin],
    system_prompt_builder: Optional[Callable[[], str]] = None,
    checkpointer=None,
):
    """Build and compile a LangGraph agent from the given plugins."""
    for p in plugins:
        await p.setup()

    all_tools = []
    for p in plugins:
        all_tools.extend(p.tools())

    if system_prompt_builder is None:

        def system_prompt_builder():
            now = datetime.now(ZoneInfo("America/New_York")).strftime(
                "%A, %Y-%m-%d %H:%M:%S"
            )
            return f"You are a helpful assistant named Wendy. Current date and time: {now} EST/EDT"

    llm = get_llm_service().get_llm()
    agent_node, tool_node = create_nodes(all_tools, llm, system_prompt_builder)

    def should_continue(state: AgentState) -> str:
        return state["next_action"]

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "agent")

    if checkpointer is None:
        checkpointer = await get_checkpointer()

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Agent graph created successfully.")
    return compiled
