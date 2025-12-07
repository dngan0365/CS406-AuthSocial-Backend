from pydantic import BaseModel
from datetime import datetime

class NotificationResponse(BaseModel):
    id: str
    recipient_id: str
    actor_id: str | None
    post_id: str | None
    type: str
    body: str | None
    is_read: bool
    created_at: datetime
    actor: dict | None = None