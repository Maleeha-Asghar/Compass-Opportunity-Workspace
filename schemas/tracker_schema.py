from datetime import date

from pydantic import BaseModel


class TrackerItem(BaseModel):
    opportunity_id: str
    status: str
    next_task: str | None = None
    deadline: date | None = None
