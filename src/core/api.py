from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.core.registry import AgentRegistry

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    agent: str = "personal"


class ChatResponse(BaseModel):
    response: str


def create_app(
    registry: AgentRegistry,
    api_key: str,
    title: str = "Agent API",
) -> FastAPI:
    app = FastAPI(title=title)

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, x_api_key: str = Header(...)):
        if x_api_key != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        try:
            graph = registry.get(request.agent)
        except KeyError as err:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown agent: {request.agent}",
            ) from err

        logger.info(
            f"API chat request: agent={request.agent} user_id={request.user_id}"
        )

        today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        thread_id = f"{request.agent}_{request.user_id}_{today}"

        result = await graph.ainvoke(
            {
                "user_id": request.user_id,
                "messages": [HumanMessage(content=request.message)],
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        content = result["messages"][-1].content
        if isinstance(content, list):
            content = "".join(
                block["text"] for block in content if block.get("type") == "text"
            )
        return ChatResponse(response=content)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
