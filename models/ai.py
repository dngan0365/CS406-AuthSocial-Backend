from pydantic import BaseModel

class AICheckResponse(BaseModel):
    status: str  # "checking", "approved_non_ai", "rejected_ai"
    confidence: float | None = None
    message: str