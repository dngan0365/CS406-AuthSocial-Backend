from fastapi import Depends, HTTPException, status, Header
from typing import Optional
from services.supabase_client import get_supabase_client
from supabase import Client

async def get_current_user(
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy user hiện tại từ JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    
    try:
        # Verify token với Supabase
        user = supabase.auth.get_user(token)
        return user.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy user nếu có token, không bắt buộc"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split(" ")[1]
    
    try:
        user = supabase.auth.get_user(token)
        return user.user
    except:
        return None

async def require_admin(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Kiểm tra user có role admin"""
    profile = supabase.table("profiles").select("role").eq("id", current_user.id).execute()
    
    if not profile.data or profile.data[0]["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user