from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    
    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    
    # Storage
    storage_bucket: str = "media"
    
    # AI Model
    model_path: str = "ml_models/best_model.pth"
    device: str = "cpu"
    
    # Frontend URL
    frontend_url: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()