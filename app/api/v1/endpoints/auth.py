from fastapi import APIRouter, Depends, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import (
    UserCreate, LoginRequest, TokenResponse, RefreshTokenRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest, UserResponse
)
from app.api.deps import get_current_user, get_admin_user
from app.models import User
from app.repositories.repositories import UserRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])




@router.post("/login", response_model=TokenResponse)
async def login(login_in: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Login with email and password, returns JWT tokens."""
    service = AuthService(db)
    return await service.login(login_in, request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    service = AuthService(db)
    return await service.refresh_token(body.refresh_token)


@router.post("/logout")
async def logout(
    body: RefreshTokenRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout and revoke refresh token."""
    service = AuthService(db)
    await service.logout(body.refresh_token, current_user.id, request)
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send password reset email."""
    service = AuthService(db)
    message = await service.forgot_password(body.email)
    return {"message": message}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using reset token."""
    service = AuthService(db)
    await service.reset_password(body.token, body.new_password)
    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password for logged-in user."""
    from app.core.security import verify_password, get_password_hash
    from app.repositories.repositories import UserRepository
    if not verify_password(body.current_password, current_user.hashed_password):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    repo = UserRepository(db)
    await repo.update(current_user.id, {"hashed_password": get_password_hash(body.new_password)})
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return current_user
