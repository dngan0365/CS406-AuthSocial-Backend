from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import Client
from typing import List
from services.supabase_client import get_supabase_client
from services.ai_service import get_ai_service, AIService
from dependencies import get_current_user
from models.ai import AICheckResponse

router = APIRouter(prefix="/posts/{post_id}", tags=["AI Detection"])

@router.post("/check_ai", response_model=AICheckResponse)
async def check_ai(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
    ai_service: AIService = Depends(get_ai_service)
):
    """Kiểm tra media của post có phải AI không"""
    # Check ownership
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not the post owner")
    
    # Get all media
    media = supabase.table("post_media").select("*").eq("post_id", post_id).eq("media_type", "image").execute()
    
    if not media.data:
        return AICheckResponse(
            status="no_images",
            message="No images found in this post"
        )
    
    # Download images from storage
    images_bytes = []
    for m in media.data:
        file_content = supabase.storage.from_("media").download(m["storage_path"])
        images_bytes.append(file_content)
    
    # Check with AI
    result = await ai_service.check_images(images_bytes)
    
    # Create notification if approved
    if result["status"] == "approved_non_ai":
        notification_data = {
            "recipient_id": current_user.id,
            "post_id": post_id,
            "type": "post_approved",
            "body": "Your post has been approved as non-AI content"
        }
        supabase.table("notifications").insert(notification_data).execute()
    
    return AICheckResponse(**result)

@router.get("/ai_status")
async def get_ai_status(
    post_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy trạng thái AI check của post (nếu có)"""
    # This assumes you have an ai_status column in posts table
    # If not, you might need to create a separate table for AI checks
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return {"post_id": post_id, "status": "not_checked"}