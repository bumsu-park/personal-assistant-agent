import logging
from src.agent.state import AgentState
from src.services.llm import get_llm_service
from src.services.rag import get_rag_service
from src.services.calendar import (
    create_calendar_event,
    search_calendar_events,
    list_calendar_events,
    delete_calendar_event
)
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)

_calendar_tools = [
    create_calendar_event,
    search_calendar_events,
    list_calendar_events,
    delete_calendar_event
]

_llm_with_tools = get_llm_service().get_llm().bind_tools(_calendar_tools)

async def agent_node(state: AgentState) -> AgentState:
    """Main agent node that decides whether to use tools or respond directly."""
    logger.info(f"Agent Node - user: {state.user_id}")
    
    if not state.messages or not isinstance(state.messages[0], SystemMessage):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        current_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        system_msg = SystemMessage(
            content=f"You are a helpful assistant. Current date and time: {current_date} EST/EDT")
        state.messages.insert(0, system_msg)

    response = await _llm_with_tools.ainvoke(state.messages)

    state.messages.append(response)

    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info(f"LLM requested {len(response.tool_calls)} tool calls")
        state.next_action = "tools"
    else:
        logger.info("No tool calls necessary")
        state.next_action = "end"

    return state

async def tool_node(state: AgentState) -> AgentState:
    """Node that executes tools based on LLM decisions."""
    logger.info(f"Tool Node - user: {state.user_id}")
    last_message = state.messages[-1]

    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        logger.warning("Tool node called but no tool calls found")
        state.next_action = "end"
        return state

    tools_map = {
        "create_calendar_event": create_calendar_event,
        "search_calendar_events": search_calendar_events,
        "list_calendar_events": list_calendar_events,
        "delete_calendar_event": delete_calendar_event,
    }

    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        tool_id = tool_call['id']

        logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

        tool = tools_map.get(tool_name)

        if tool:
            try:
                result = tool.invoke(tool_args)
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_id)
                )
                logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                tool_messages.append(
                    ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id)
                )
        else:
            logger.error(f"Unknown tool: {tool_name}")
            tool_messages.append(
                ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_id)
            )

    # These lines MUST be outside the for loop
    state.messages.extend(tool_messages)
    state.next_action = "agent"

    return state


async def rag_node(state: AgentState) -> AgentState:
    """RAG node for document-based responses."""
    logger.info(f"RAG Node - user: {state.user_id}")

    rag_service = get_rag_service()
    
    if rag_service is not None:
        logger.warning("RAG service not available, falling back to agent")
        state.next_action = "agent"
        return state
    
    user_query = state.messages[-1].content

    retrieved_docs = rag_service.search_document(
        query=user_query,
        user_id=state.user_id,
        k=3
    )

    if not retrieved_docs:
        logger.info("No RAG documents found. Falling back to agent.")
        return await agent_node(state)

    context_text = "\n\n".join(
        f"Document {i+1}:\n{doc['content']}" for i, doc in enumerate(retrieved_docs)
    )

    context_message = SystemMessage(
        content=f"Use the following information to answer the user's query:\n\n{context_text}"
    )

    messages_with_context = state.messages[:-1] + [context_message, state.messages[-1]]

    llm_service = get_llm_service()
    response = await llm_service.get_llm().ainvoke(messages_with_context)

    state.messages.append(AIMessage(content=response.content))
    state.context["rag_used"] = True
    state.context["sources"] = [doc["metadata"].get("url", "N/A") for doc in retrieved_docs]

    logger.info(f"AI Response with RAG: {response.content}")

    return state
