from supabase import create_client, Client
from config import get_settings
from functools import lru_cache

settings = get_settings()

@lru_cache()
def get_supabase_client() -> Client:
    """Client với anon key cho operations thông thường"""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)

@lru_cache()
def get_supabase_admin_client() -> Client:
    """Client với service role key cho admin operations"""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
