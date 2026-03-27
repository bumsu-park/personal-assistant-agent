from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from typing import List, Dict, Any


class AgentState(BaseModel):
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="The list of messages exchanged in the conversation.",
    )
    user_id: str = Field(..., description="The unique identifier for the user.")
    next_action: str = Field(default="", description="Next node to route to")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context information for the agent.",
    )

    class Config:
        arbitrary_types_allowed = True
