import logging 
from langgraph.graph import StateGraph, END 
from src.agent.state import AgentState
from src.agent.nodes import agent_node, tool_node
from src.services.memory import get_checkpointer

logger = logging.getLogger(__name__)

async def create_agent_state_graph() -> StateGraph[AgentState]:
    logger.info("Creating agent state graph...")
    graph = StateGraph(AgentState)

    graph.add_node("agent",  agent_node)
    graph.add_node("tools",    tool_node)
    
    graph.set_entry_point("agent")
    
    ## Conditional Routing
    def should_continue(state: AgentState) -> str:
        return state.next_action
    
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    graph.add_edge("tools", "agent")
    
    checkpointer = await get_checkpointer()
    
    compiled_graph = graph.compile(checkpointer=checkpointer)
    logger.info("Agent state graph created successfully.")
    return compiled_graph
    
_agent_state_graph = None 

async def get_agent_state_graph() -> StateGraph:
    global _agent_state_graph
    if _agent_state_graph is None:
        _agent_state_graph = await create_agent_state_graph()
    return _agent_state_graph