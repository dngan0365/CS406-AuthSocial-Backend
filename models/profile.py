from pydantic import BaseModel
from datetime import datetime

class ProfileResponse(BaseModel):
    id: str
    username: str
    display_name: str | None
    avatar_url: str | None
    role: str
    created_at: datetime

class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None