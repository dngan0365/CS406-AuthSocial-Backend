import logging
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from models.auth import SignUpRequest, LoginRequest, AuthResponse
from services.supabase_client import get_supabase_client
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup")
async def signup(
    data: SignUpRequest,
    supabase: Client = Depends(get_supabase_client)
):
    logging.info("Signup request for email: %s", data.email)
    try:
        # 1️⃣ Create auth user with metadata
        # Dữ liệu trong 'data' sẽ được Trigger dùng để tạo profile tự động
        auth_response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {  # Lưu ý: Python client đôi khi dùng key "options" chứa "data"
                "data": {
                    "username": data.username,
                    "display_name": data.display_name or data.username
                }
            }
        })

        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )

        # 2️⃣ Check if email confirmation is required
        if auth_response.session is None:
            return {
                "message": "Please check your email to confirm your account",
                "user": auth_response.user.model_dump()
            }
        
        # 3️⃣ Return response
        # KHÔNG CẦN INSERT VÀO profiles NỮA (Trigger đã làm rồi)
        return AuthResponse(
            access_token=auth_response.session.access_token,
            user=auth_response.user.model_dump()
        )

    except Exception as e:
        logging.exception("Signup failed")
        # Bắt lỗi cụ thể từ Supabase để trả về frontend dễ hiểu hơn
        error_msg = str(e)
        if "User already registered" in error_msg:
             raise HTTPException(status_code=400, detail="Email already exists")
             
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """Login with email/password"""
    try:
        # 1. Sign in with Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

        if not auth_response.session:
            # Email not verified or wrong credentials
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not verified or invalid credentials"
            )

        # 2. Return token directly
        # Profile creation is now handled by DB Triggers, checking it here is redundant.
        return AuthResponse(
            access_token=auth_response.session.access_token,
            user=auth_response.user.model_dump()
        )

    except Exception as e:
        logging.exception("Login failed")
        # Check specific Supabase error if needed, usually generic 401 is safest
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    """Get current logged-in user info"""
    return current_user