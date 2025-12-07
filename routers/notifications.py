from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from typing import List
from services.supabase_client import get_supabase_client
from dependencies import get_current_user
from models.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy danh sách notifications của user"""
    query = supabase.table("notifications").select("*").eq("recipient_id", current_user.id)
    
    if unread_only:
        query = query.eq("is_read", False)
    
    # Pagination
    offset = (page - 1) * limit
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    notifications = result.data
    
    # Enrich with actor info
    for notif in notifications:
        if notif.get("actor_id"):
            actor = supabase.table("profiles").select("*").eq("id", notif["actor_id"]).execute()
            notif["actor"] = actor.data[0] if actor.data else None
        else:
            notif["actor"] = None
    
    return notifications

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Đánh dấu notification đã đọc"""
    # Check ownership
    notif = supabase.table("notifications").select("*").eq("id", notification_id).execute()
    
    if not notif.data:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notif.data[0]["recipient_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your notification")
    
    # Update
    result = supabase.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
    
    return result.data[0]

@router.post("/mark-all-read")
async def mark_all_read(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Đánh dấu tất cả notifications đã đọc"""
    supabase.table("notifications").update({"is_read": True}).eq("recipient_id", current_user.id).eq("is_read", False).execute()
    
    return {"message": "All notifications marked as read"}

@router.get("/unread-count")
async def get_unread_count(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy số lượng notifications chưa đọc"""
    result = supabase.table("notifications").select("id", count="exact").eq("recipient_id", current_user.id).eq("is_read", False).execute()
    
    return {"count": result.count or 0}