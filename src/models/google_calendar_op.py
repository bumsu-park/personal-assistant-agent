from pydantic import BaseModel
from typing import Optional, Literal
# from datetime import datetime

class GoogleCalendarOperation(BaseModel):
    operation: Literal["create_event", "list_events", "search_events", "update_event", "delete_event", "unclear"]
    summary: Optional[str] = None 
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None
    locaton: Optional[str] = None
    search_query: Optional[str] = None
    max_results: Optional[int] = 5
    
    