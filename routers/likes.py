from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from typing import List
from services.supabase_client import get_supabase_client
from dependencies import get_current_user

router = APIRouter(prefix="/posts/{post_id}", tags=["Likes"])

@router.post("/like", status_code=status.HTTP_201_CREATED)
async def like_post(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Thêm like cho post"""
    # Check if post exists
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if already liked
    existing_like = supabase.table("post_likes").select("id").eq("post_id", post_id).eq("user_id", current_user.id).execute()
    
    if existing_like.data:
        raise HTTPException(status_code=400, detail="Already liked")
    
    # Create like
    like_data = {
        "post_id": post_id,
        "user_id": current_user.id
    }
    
    result = supabase.table("post_likes").insert(like_data).execute()
    
    # Update like count
    new_count = post.data[0]["like_count"] + 1
    supabase.table("posts").update({"like_count": new_count}).eq("id", post_id).execute()
    
    # Create notification for post owner (if not self-like)
    if post.data[0]["owner_id"] != current_user.id:
        notification_data = {
            "recipient_id": post.data[0]["owner_id"],
            "actor_id": current_user.id,
            "post_id": post_id,
            "type": "like",
            "body": "liked your post"
        }
        supabase.table("notifications").insert(notification_data).execute()
    
    return result.data[0]

@router.delete("/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_post(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Hủy like post"""
    # Check if post exists
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if liked
    existing_like = supabase.table("post_likes").select("id").eq("post_id", post_id).eq("user_id", current_user.id).execute()
    
    if not existing_like.data:
        raise HTTPException(status_code=400, detail="Not liked yet")
    
    # Delete like
    supabase.table("post_likes").delete().eq("post_id", post_id).eq("user_id", current_user.id).execute()
    
    # Update like count
    new_count = max(0, post.data[0]["like_count"] - 1)
    supabase.table("posts").update({"like_count": new_count}).eq("id", post_id).execute()
    
    return None

@router.get("/likes")
async def get_post_likes(
    post_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy danh sách users đã like post"""
    # Get likes with user info
    likes = supabase.table("post_likes").select("*, user:user_id(*)").eq("post_id", post_id).execute()
    
    # Extract user profiles
    users = []
    for like in likes.data:
        if like.get("user"):
            # Get full profile
            profile = supabase.table("profiles").select("*").eq("id", like["user_id"]).execute()
            if profile.data:
                users.append(profile.data[0])
    
    return users