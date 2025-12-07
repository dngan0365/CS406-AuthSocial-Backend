from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import Client
from models.profile import ProfileResponse, ProfileUpdate
from services.supabase_client import get_supabase_client
from dependencies import get_current_user
from config import get_settings
import uuid

router = APIRouter(prefix="/profiles", tags=["Profiles"])
settings = get_settings()

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy profile của user hiện tại"""
    profile = supabase.table("profiles").select("*").eq("id", current_user.id).execute()
    
    if not profile.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile.data[0]

@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(
    data: ProfileUpdate,
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Cập nhật profile của user hiện tại"""
    update_data = data.model_dump(exclude_unset=True)
    
    result = supabase.table("profiles").update(update_data).eq("id", current_user.id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return result.data[0]

@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Upload avatar"""
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Upload to storage
    file_content = await file.read()
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    storage_path = f"avatars/{current_user.id}/{uuid.uuid4()}.{file_ext}"
    
    supabase.storage.from_(settings.storage_bucket).upload(
        storage_path,
        file_content,
        {"content-type": file.content_type}
    )
    
    # Get public URL
    avatar_url = supabase.storage.from_(settings.storage_bucket).get_public_url(storage_path)
    
    # Update profile
    supabase.table("profiles").update({"avatar_url": avatar_url}).eq("id", current_user.id).execute()
    
    return {"avatar_url": avatar_url}

@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy profile của user bất kỳ"""
    profile = supabase.table("profiles").select("*").eq("id", user_id).execute()
    
    if not profile.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile.data[0]

@router.get("/{username}/by-username", response_model=ProfileResponse)
async def get_profile_by_username(
    username: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Lấy profile theo username"""
    profile = supabase.table("profiles").select("*").eq("username", username).execute()
    
    if not profile.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile.data[0]