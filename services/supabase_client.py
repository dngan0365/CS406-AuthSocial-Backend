from supabase import create_client, Client
from config import get_settings
from functools import lru_cache
import logging

settings = get_settings()

@lru_cache()
def get_supabase_admin_client() -> Client:
    """
    Supabase admin client with service_role key (không hết hạn)
    Dùng cho background tasks và operations không cần user context
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key
    )

def get_supabase_client(token: str = None) -> Client:
    """
    Supabase client với user token (có thể hết hạn)
    
    Args:
        token: JWT token từ request header Authorization
    
    Returns:
        Client với token được set
    """
    # Tạo client mới mỗi lần để tránh cache token cũ
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key
    )
    
    if token:
        # Set token cho requests cần authentication
        client.auth.set_session(token)
    
    return client

# ========================================
# Wrapper function cho dependency injection
# ========================================

def get_supabase_client_dependency():
    """
    FastAPI dependency - trả về admin client
    Dùng trong các endpoint không cần user-specific permissions
    """
    return get_supabase_admin_client()