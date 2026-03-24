import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.agent.state import AgentState
from src.agent.graph import get_agent_state_graph
from src.config import Config

logger = logging.getLogger(__name__)

app = FastAPI(title="Wendy API")


class ChatRequest(BaseModel):
    message: str
    user_id: str = "ios_user"


class ChatResponse(BaseModel):
    response: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, x_api_key: str = Header(...)):
    if x_api_key != Config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info(f"API chat request from user_id={request.user_id}")

    state = AgentState(
        user_id=request.user_id,
        messages=[HumanMessage(content=request.message)],
    )
    graph = await get_agent_state_graph()
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    result = await graph.ainvoke(
        state,
        config={"configurable": {"thread_id": f"{request.user_id}_{today}"}},
    )

    ai_response = result["messages"][-1].content
    return ChatResponse(response=ai_response)


@app.get("/health")
async def health():
    return {"status": "ok"}
