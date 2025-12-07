from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from typing import List
from services.supabase_client import get_supabase_admin_client
from dependencies import require_admin
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["Admin"])

class ReviewPostRequest(BaseModel):
    ai_status: str  # "approved_non_ai" or "rejected_ai"

class UpdateRoleRequest(BaseModel):
    role: str  # "user" or "admin"

@router.get("/posts")
async def get_all_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    current_admin = Depends(require_admin),
    supabase: Client = Depends(get_supabase_admin_client)
):
    """Admin: Lấy tất cả posts (bao gồm private)"""
    query = supabase.table("posts").select("*")
    
    # Filter by status if provided
    # Note: You might need to add an ai_status column to posts table
    # if status:
    #     query = query.eq("ai_status", status)
    
    # Pagination
    offset = (page - 1) * limit
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    posts = result.data
    
    # Enrich with owner info
    for post in posts:
        owner = supabase.table("profiles").select("*").eq("id", post["owner_id"]).execute()
        post["owner"] = owner.data[0] if owner.data else None
        
        media = supabase.table("post_media").select("*").eq("post_id", post["id"]).order("order").execute()
        post["media"] = media.data
    
    return posts

@router.patch("/posts/{post_id}/review")
async def review_post(
    post_id: str,
    data: ReviewPostRequest,
    current_admin = Depends(require_admin),
    supabase: Client = Depends(get_supabase_admin_client)
):
    """Admin: Duyệt hoặc từ chối post"""
    # Check if post exists
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Update ai_status (you might need to add this column)
    # supabase.table("posts").update({"ai_status": data.ai_status}).eq("id", post_id).execute()
    
    # Create notification for post owner
    notification_body = "approved" if data.ai_status == "approved_non_ai" else "rejected due to AI content"
    notification_data = {
        "recipient_id": post.data[0]["owner_id"],
        "post_id": post_id,
        "type": "admin_review",
        "body": f"Your post has been {notification_body}"
    }
    supabase.table("notifications").insert(notification_data).execute()
    
    return {"message": "Post reviewed successfully", "status": data.ai_status}

@router.delete("/posts/{post_id}")
async def delete_post_admin(
    post_id: str,
    current_admin = Depends(require_admin),
    supabase: Client = Depends(get_supabase_admin_client)
):
    """Admin: Xóa bất kỳ post nào"""
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Create notification before deleting
    notification_data = {
        "recipient_id": post.data[0]["owner_id"],
        "type": "post_deleted",
        "body": "Your post has been removed by an administrator"
    }
    supabase.table("notifications").insert(notification_data).execute()
    
    # Delete post
    supabase.table("posts").delete().eq("id", post_id).execute()
    
    return {"message": "Post deleted successfully"}

@router.get("/users")
async def get_all_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_admin = Depends(require_admin),
    supabase: Client = Depends(get_supabase_admin_client)
):
    """Admin: Lấy danh sách tất cả users"""
    offset = (page - 1) * limit
    result = supabase.table("profiles").select("*").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    return result.data

@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    data: UpdateRoleRequest,
    current_admin = Depends(require_admin),
    supabase: Client = Depends(get_supabase_admin_client)
):
    """Admin: Thay đổi role của user"""
    if data.role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    result = supabase.table("profiles").update({"role": data.role}).eq("id", user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    return result.data[0]

@router.get("/stats")
async def get_admin_stats(
    current_admin = Depends(require_admin),
    supabase: Client = Depends(get_supabase_admin_client)
):
    """Admin: Thống kê tổng quan"""
    # Count users
    users = supabase.table("profiles").select("id", count="exact").execute()
    
    # Count posts
    posts = supabase.table("posts").select("id", count="exact").execute()
    
    # Count public posts
    public_posts = supabase.table("posts").select("id", count="exact").eq("is_private", False).execute()
    
    # Count total likes
    likes = supabase.table("post_likes").select("id", count="exact").execute()
    
    return {
        "total_users": users.count or 0,
        "total_posts": posts.count or 0,
        "public_posts": public_posts.count or 0,
        "private_posts": (posts.count or 0) - (public_posts.count or 0),
        "total_likes": likes.count or 0
    }