import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Awaitable
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.core.state import AgentState
from src.core.config import Config

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    response: str


def create_app(
    graph_factory: Callable[[], Awaitable],
    title: str = "Agent API",
) -> FastAPI:
    app = FastAPI(title=title)
    _graph = None

    async def get_graph():
        nonlocal _graph
        if _graph is None:
            _graph = await graph_factory()
        return _graph

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, x_api_key: str = Header(...)):
        if x_api_key != Config.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")

        logger.info(f"API chat request from user_id={request.user_id}")

        state = AgentState(
            user_id=request.user_id,
            messages=[HumanMessage(content=request.message)],
        )
        graph = await get_graph()
        today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": f"{request.user_id}_{today}"}},
        )
        return ChatResponse(response=result["messages"][-1].content)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
