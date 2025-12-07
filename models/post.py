from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PostCreate(BaseModel):
    content: str | None = None
    is_private: bool = False

class PostUpdate(BaseModel):
    content: str | None = None
    is_private: bool | None = None

class MediaResponse(BaseModel):
    id: str
    storage_path: str
    media_type: str
    order: int
    url: str | None = None
    ai_perc: float | None = None  # Confidence score từ AI detection
    is_ai: bool | None = None  # True nếu ảnh được tạo bởi AI

class PostResponse(BaseModel):
    id: str
    owner_id: str
    owner_name: str | None
    owner_avatar: str | None
    content: str | None
    is_private: bool
    like_count: int
    created_at: datetime
    status: str | None = None  # pending, approved, rejected, error
    ai_perc: float | None = None  # Phần trăm ảnh AI trong post
    media: List[MediaResponse] = []
    is_liked: bool = False