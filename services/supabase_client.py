import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from supabase import Client
from typing import List
from models.post import PostCreate, PostUpdate, PostResponse
from services.supabase_client import get_supabase_admin_client  # ← Changed
from services.ai_service import get_ai_service, AIService
from dependencies import get_current_user, get_current_user_optional
from pydantic import BaseModel
from config import get_settings
import uuid

settings = get_settings()

class LinkMediaRequest(BaseModel):
    storage_path: str
    media_type: str
    order: int

router = APIRouter(prefix="/posts", tags=["Posts"])

# ========================================
# BACKGROUND TASKS - Dùng admin client
# ========================================

async def process_ai_detection(
    post_id: str,
    ai_service: AIService
):
    """
    Background task để đánh giá AI cho post
    Sử dụng admin client để tránh JWT expiration
    """
    # Tạo admin client mới trong background task
    supabase = get_supabase_admin_client()
    
    try:
        # Lấy tất cả media của post
        media_result = supabase.table("post_media").select("*").eq("post_id", post_id).eq("media_type", "image").execute()
        
        if not media_result.data:
            # Không có ảnh, approved luôn
            supabase.table("posts").update({
                "status": "approved",
                "ai_perc": None  # Set NULL thay vì 0.0
            }).eq("id", post_id).execute()
            
            # Get post owner
            post = supabase.table("posts").select("owner_id").eq("id", post_id).execute()
            if post.data:
                notification_data = {
                    "recipient_id": post.data[0]["owner_id"],
                    "post_id": post_id,
                    "type": "post_approved",
                    "body": "Your post has been approved"
                }
                supabase.table("notifications").insert(notification_data).execute()
            return
        
        # Đánh giá từng ảnh
        ai_count = 0
        total_images = len(media_result.data)
        
        for media in media_result.data:
            try:
                # Download image
                file_content = supabase.storage.from_(settings.storage_bucket).download(media["storage_path"])
                
                # Check AI
                result = await ai_service.check_single_image(file_content)
                
                # Update media record
                media_update = {"is_ai": result["is_ai"]}
                if result["confidence"] > 0:
                    media_update["ai_perc"] = result["confidence"]
                
                supabase.table("post_media").update(media_update).eq("id", media["id"]).execute()
                
                if result["is_ai"]:
                    ai_count += 1
                    
            except Exception as e:
                logging.error(f"Error processing media {media['id']}: {e}")
                continue
        
        # Tính phần trăm AI cho post
        ai_percentage = (ai_count / total_images) * 100 if total_images > 0 else 0
            
        # Update post status
        new_status = "rejected" if ai_percentage > 80 else "approved"
        
        post_update = {
            "status": new_status,
            "ai_perc": ai_percentage if ai_percentage > 0 else None
        }
        
        supabase.table("posts").update(post_update).eq("id", post_id).execute()
        
        # Send notification
        post = supabase.table("posts").select("owner_id").eq("id", post_id).execute()
        if post.data:
            if new_status == "approved":
                body = f"Your post has been approved! AI detection score: {ai_percentage:.1f}%"
            else:
                body = f"Your post was rejected due to high AI content: {ai_percentage:.1f}%"
            
            notification_data = {
                "recipient_id": post.data[0]["owner_id"],
                "actor_id": None,
                "post_id": post_id,
                "type": f"post_{new_status}",
                "body": body
            }
            
            supabase.table("notifications").insert(notification_data).execute()
            
    except Exception as e:
        logging.error(f"Error in AI detection for post {post_id}: {e}")
        # Mark as error status
        supabase.table("posts").update({
            "status": "error"
        }).eq("id", post_id).execute()

# ========================================
# ENDPOINTS - Đổi dependency injection
# ========================================

@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    data: PostCreate,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client),  # ← Changed
    ai_service: AIService = Depends(get_ai_service)
):
    """Tạo post mới với status pending"""
    post_data = {
        "owner_id": current_user.id,
        "content": data.content,
        "is_private": data.is_private,
        "status": "pending"
    }
    
    result = supabase.table("posts").insert(post_data).execute()
    post = result.data[0]
    
    # Schedule AI detection trong background (không truyền supabase)
    background_tasks.add_task(process_ai_detection, post["id"], ai_service)
    
    # Get owner info
    owner = supabase.table("profiles").select("*").eq("id", post["owner_id"]).execute()
    post["owner_name"] = owner.data[0].get("display_name") if owner.data else None
    post["owner_avatar"] = owner.data[0].get("avatar_url") if owner.data else None
    post["media"] = []
    post["is_liked"] = False
    
    return post

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: str,
    current_user = Depends(get_current_user_optional),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Lấy chi tiết post"""
    post_result = supabase.table("posts").select("*").eq("id", post_id).execute()
    if not post_result.data:
        raise HTTPException(status_code=404, detail="Post not found")

    post = post_result.data[0]

    # Privacy check
    if post["is_private"] and (not current_user or post["owner_id"] != current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Status check
    if post["status"] in ["pending", "rejected", "error"]:
        if not current_user or post["owner_id"] != current_user.id:
            raise HTTPException(status_code=404, detail="Post not found")

    # Owner
    owner_data = supabase.table("profiles").select("*").eq("id", post["owner_id"]).execute()
    owner = owner_data.data[0] if owner_data.data else None

    post["owner_name"] = owner.get("display_name") if owner else None
    post["owner_avatar"] = owner.get("avatar_url") if owner else None

    # Media
    media = supabase.table("post_media").select("*").eq("post_id", post_id).order("order").execute()
    for m in media.data:
        public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(m["storage_path"])
        m["url"] = public_url
    post["media"] = media.data

    # Like status
    post["is_liked"] = False
    if current_user:
        like = (
            supabase.table("post_likes")
            .select("id")
            .eq("post_id", post_id)
            .eq("user_id", current_user.id)
            .execute()
        )
        post["is_liked"] = len(like.data) > 0

    return post

@router.get("", response_model=List[PostResponse])
async def get_posts(
    owner_id: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user = Depends(get_current_user_optional),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Lấy danh sách posts"""
    query = supabase.table("posts").select("*")
    
    if owner_id:
        query = query.eq("owner_id", owner_id)
        
        if current_user and owner_id == current_user.id:
            pass  # Không filter
        else:
            query = query.eq("status", "approved").eq("is_private", False)
    else:
        # Feed
        if current_user:
            query = query.or_(
                f"and(status.eq.approved,is_private.eq.false),"
                f"owner_id.eq.{current_user.id}"
            )
        else:
            query = query.eq("status", "approved").eq("is_private", False)
    
    # Pagination
    offset = (page - 1) * limit
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    posts = result.data
    
    # Batch fetch likes
    user_liked_posts = set()
    if current_user:
        try:
            post_ids = [p["id"] for p in posts]
            if post_ids:
                likes_result = supabase.table("post_likes")\
                    .select("post_id")\
                    .eq("user_id", current_user.id)\
                    .in_("post_id", post_ids)\
                    .execute()
                
                user_liked_posts = {like["post_id"] for like in likes_result.data}
        except Exception as e:
            logging.error(f"Error fetching user likes: {e}")
    
    # Enrich posts
    for post in posts:
        # Owner info
        owner_data = supabase.table("profiles").select("*").eq("id", post["owner_id"]).execute()
        if owner_data.data:
            owner = owner_data.data[0]
            post["owner_name"] = owner.get("display_name")
            post["owner_avatar"] = owner.get("avatar_url")
        else:
            post["owner_name"] = None
            post["owner_avatar"] = None

        # Media
        media = supabase.table("post_media").select("*").eq("post_id", post["id"]).order("order").execute()
        for m in media.data:
            public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(m["storage_path"])
            m["url"] = public_url
        post["media"] = media.data
        post["is_liked"] = post["id"] in user_liked_posts

    return posts

# ========================================
# Các endpoints còn lại tương tự
# Thay tất cả: supabase: Client = Depends(get_supabase_client)
# Thành: supabase: Client = Depends(get_supabase_admin_client)
# ========================================

@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    data: PostUpdate,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Cập nhật post"""
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not the post owner")
    
    update_data = data.model_dump(exclude_unset=True)
    result = supabase.table("posts").update(update_data).eq("id", post_id).execute()
    
    return await get_post(post_id, current_user, supabase)

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Xóa post"""
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not the post owner")
    
    supabase.table("posts").delete().eq("id", post_id).execute()
    
    return None

@router.post("/{post_id}/like", status_code=status.HTTP_200_OK)
async def like_post(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Like a post"""
    post = supabase.table("posts").select("id, owner_id, like_count, status").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post_data = post.data[0]
    
    if post_data.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Cannot like this post")
    
    existing_like = supabase.table("post_likes").select("id").eq("post_id", post_id).eq("user_id", current_user.id).execute()
    
    if existing_like.data:
        return {"message": "Already liked", "liked": True}
    
    like_data = {
        "post_id": post_id,
        "user_id": current_user.id
    }
    
    supabase.table("post_likes").insert(like_data).execute()
    
    new_like_count = post_data.get("like_count", 0) + 1
    supabase.table("posts").update({"like_count": new_like_count}).eq("id", post_id).execute()
    
    if post_data["owner_id"] != current_user.id:
        user_profile = supabase.table("profiles").select("display_name, username").eq("id", current_user.id).execute()
        display_name = user_profile.data[0].get("display_name") if user_profile.data else None
        username = user_profile.data[0].get("username") if user_profile.data else "Someone"
        
        name_to_show = display_name or username
        
        notification_data = {
            "recipient_id": post_data["owner_id"],
            "actor_id": current_user.id,
            "post_id": post_id,
            "type": "like",
            "body": f"{name_to_show} liked your post"
        }
        
        supabase.table("notifications").insert(notification_data).execute()
    
    return {"message": "Post liked", "liked": True}

@router.delete("/{post_id}/like", status_code=status.HTTP_200_OK)
async def unlike_post(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Unlike a post"""
    post = supabase.table("posts").select("id, like_count").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    result = supabase.table("post_likes").delete().eq("post_id", post_id).eq("user_id", current_user.id).execute()
    
    if result.data:
        new_like_count = max(0, post.data[0].get("like_count", 0) - 1)
        supabase.table("posts").update({"like_count": new_like_count}).eq("id", post_id).execute()
    
    return {"message": "Post unliked", "liked": False}

@router.get("/{post_id}/likes", status_code=status.HTTP_200_OK)
async def get_post_likes(
    post_id: str,
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Get all likes for a post with user details"""
    post = supabase.table("posts").select("id").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    likes = supabase.table("post_likes").select("*, profiles(*)").eq("post_id", post_id).execute()
    
    return {
        "post_id": post_id,
        "likes_count": len(likes.data),
        "likes": likes.data
    }

@router.get("/{post_id}/liked", status_code=status.HTTP_200_OK)
async def is_post_liked(
    post_id: str,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Check if current user has liked the post"""
    post = supabase.table("posts").select("id").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    like = supabase.table("post_likes")\
        .select("id")\
        .eq("post_id", post_id)\
        .eq("user_id", current_user.id)\
        .execute()
    
    return {"post_id": post_id, "liked": len(like.data) > 0}

@router.post("/{post_id}/media/link")
async def link_media_to_post(
    post_id: str,
    media_data: LinkMediaRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client),  # ← Changed
    ai_service: AIService = Depends(get_ai_service)
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
    
    if media_data.media_type == "image":
        background_tasks.add_task(process_ai_detection, post_id, ai_service)
    
    return media

@router.post("/{post_id}/media", status_code=status.HTTP_201_CREATED)
async def upload_media(
    post_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client),  # ← Changed
    ai_service: AIService = Depends(get_ai_service)
):
    """Upload media cho post và trả về public URL"""
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not the post owner")
    
    content_type = file.content_type or ""
    if content_type.startswith("image"):
        media_type = "image"
    elif content_type.startswith("video"):
        media_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_content = await file.read()
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    storage_path = f"{post_id}/{uuid.uuid4()}.{file_ext}"
    
    supabase.storage.from_(settings.storage_bucket).upload(
        storage_path,
        file_content,
        {"content-type": content_type}
    )
    
    existing_media = supabase.table("post_media").select("order").eq("post_id", post_id).execute()
    max_order = max([m["order"] for m in existing_media.data], default=-1)
    
    media_data = {
        "post_id": post_id,
        "storage_path": storage_path,
        "media_type": media_type,
        "order": max_order + 1
    }
    
    result = supabase.table("post_media").insert(media_data).execute()
    media = result.data[0]

    public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(storage_path)
    media["url"] = public_url

    if media_type == "image" and background_tasks:
        background_tasks.add_task(process_ai_detection, post_id, ai_service)

    return media

@router.get("/{post_id}/media")
async def get_media(
    post_id: str,
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Lấy danh sách media của post"""
    media = supabase.table("post_media").select("*").eq("post_id", post_id).order("order").execute()
    
    for m in media.data:
        public_url = supabase.storage.from_(settings.storage_bucket).get_public_url(m["storage_path"])
        m["url"] = public_url
    
    return media.data

@router.delete("/{post_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    post_id: str,
    media_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin_client),  # ← Changed
    ai_service: AIService = Depends(get_ai_service)
):
    """Xóa media"""
    post = supabase.table("posts").select("*").eq("id", post_id).execute()
    
    if not post.data or post.data[0]["owner_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    media = supabase.table("post_media").select("*").eq("id", media_id).execute()
    
    if not media.data:
        raise HTTPException(status_code=404, detail="Media not found")
    
    was_image = media.data[0]["media_type"] == "image"
    
    supabase.storage.from_(settings.storage_bucket).remove([media.data[0]["storage_path"]])
    
    supabase.table("post_media").delete().eq("id", media_id).execute()
    
    if was_image:
        background_tasks.add_task(process_ai_detection, post_id, ai_service)
    
    return None

@router.get("/{post_id}/ai_status")
async def get_ai_status(
    post_id: str,
    current_user = Depends(get_current_user_optional),
    supabase: Client = Depends(get_supabase_admin_client)  # ← Changed
):
    """Lấy trạng thái AI check của post"""
    post = supabase.table("posts").select("status, ai_perc").eq("id", post_id).execute()
    
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post_data = post.data[0]
    
    if post_data.get("status") in ["pending", "rejected"]:
        post_full = supabase.table("posts").select("owner_id").eq("id", post_id).execute()
        if not current_user or post_full.data[0]["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    media = supabase.table("post_media").select("id, media_type, ai_perc, is_ai").eq("post_id", post_id).execute()
    
    return {
        "post_id": post_id,
        "status": post_data.get("status"),
        "ai_perc": post_data.get("ai_perc"),
        "media": media.data
    }