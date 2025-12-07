from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from supabase import Client
from typing import List
from services.supabase_client import get_supabase_client
from dependencies import get_current_user
from config import get_settings
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/media", tags=["Media"])
settings = get_settings()

class LinkMediaRequest(BaseModel):
    storage_path: str
    media_type: str
    order: int

@router.post("/upload-temp")
async def upload_temp_media(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Upload media to storage and return URL (before post creation)"""
    content_type = file.content_type or ""
    
    if content_type.startswith("image"):
        media_type = "image"
    elif content_type.startswith("video"):
        media_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_content = await file.read()
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    storage_path = f"temp/{uuid.uuid4()}.{file_ext}"
    
    supabase.storage.from_(settings.storage_bucket).upload(
        storage_path,
        file_content,
        {"content-type": content_type}
    )
    
    public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(storage_path)
    
    return {
        "id": str(uuid.uuid4()),
        "url": public_url,
        "storage_path": storage_path,
        "media_type": media_type
    }

@router.get("/url")
async def get_media_url(
    path: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get public URL for a storage path"""
    public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(path)
    return {"url": public_url}

# FIX: Moved to posts router - this should be in posts.py
posts_router = APIRouter(prefix="/posts", tags=["Posts"])

@posts_router.post("/{post_id}/media/link")
async def link_media_to_post(
    post_id: str,
    media_data: LinkMediaRequest,  # FIX: Use Pydantic model instead of dict
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Link already-uploaded media to a post"""
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data or post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    media_record = {
        "post_id": post_id,
        "storage_path": media_data.storage_path,
        "media_type": media_data.media_type,
        "order": media_data.order
    }
    
    result = supabase.table("post_media").insert(media_record).execute()
    media = result.data[0]
    
    public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(media["storage_path"])
    media["url"] = public_url
    
    return media

@posts_router.post("/{post_id}/media", status_code=status.HTTP_201_CREATED)
async def upload_media(
    post_id: str,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Upload media cho post và trả về public URL"""
    # Check post ownership
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not the post owner")
    
    # Determine media type
    content_type = file.content_type or ""
    if content_type.startswith("image"):
        media_type = "image"
    elif content_type.startswith("video"):
        media_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Upload to storage
    file_content = await file.read()
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    storage_path = f"{post_id}/{uuid.uuid4()}.{file_ext}"
    
    supabase.storage.from_(settings.storage_bucket).upload(
        storage_path,
        file_content,
        {"content-type": content_type}
    )
    
    # Get current max order
    existing_media = supabase.table("post_media").select("order").eq("post_id", post_id).execute()
    max_order = max([m["order"] for m in existing_media.data], default=-1)
    
    # Create media record
    media_data = {
        "post_id": post_id,
        "storage_path": storage_path,
        "media_type": media_type,
        "order": max_order + 1
    }
    
    result = supabase.table("post_media").insert(media_data).execute()
    media = result.data[0]

    # **Get public URL**
    public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(storage_path)
    media["url"] = public_url

    return media

@posts_router.get("/{post_id}/media")
async def get_media(
    post_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy danh sách media của post"""
    media = supabase.table("post_media").select("*").eq("post_id", post_id).order("order").execute()
    
    # Generate public URLs
    for m in media.data:
        public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(m["storage_path"])
        m["url"] = public_url
    
    return media.data

@posts_router.delete("/{post_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    post_id: str,
    media_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Xóa media"""
    # Check post ownership
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data or post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get media
    media = supabase.table("post_media").select("*").eq("id", media_id).execute()
    
    if not media.data:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Delete from storage
    supabase.storage.from_(settings.storage_bucket).remove([media.data[0]["storage_path"]])
    
    # Delete record
    supabase.table("post_media").delete().eq("id", media_id).execute()
    
    return None

