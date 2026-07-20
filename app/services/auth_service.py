from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime
from fastapi import HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, verify_token, create_password_reset_token,
    verify_password_reset_token
)
from app.core.config import settings
from app.repositories.repositories import UserRepository, RefreshTokenRepository, AuditLogRepository
from app.schemas.user import UserCreate, LoginRequest, TokenResponse
from app.models import User, AuditAction


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)
        self.audit_repo = AuditLogRepository(db)

    async def login(self, login_in: LoginRequest, request: Request) -> TokenResponse:
        user = await self.user_repo.get_by_email(login_in.email)

        if not user or not verify_password(login_in.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is {user.status}"
            )

        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        from datetime import timedelta
        await self.token_repo.create({
            "user_id": user.id,
            "token": refresh_token,
            "expires_at": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        })

        # Update last login
        await self.user_repo.update(user.id, {"last_login": datetime.utcnow()})

        await self.audit_repo.create_log(
            user_id=user.id,
            action=AuditAction.LOGIN,
            resource_type="user",
            resource_id=str(user.id),
            description=f"User logged in",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_token(self, token: str) -> TokenResponse:
        subject = verify_token(token, token_type="refresh")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        db_token = await self.token_repo.get_by_token(token)
        if not db_token or db_token.is_revoked or db_token.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

        # Revoke old token
        await self.token_repo.update(db_token.id, {"is_revoked": True})

        # Issue new tokens
        access_token = create_access_token(subject=subject)
        new_refresh = create_refresh_token(subject=subject)

        from datetime import timedelta
        await self.token_repo.create({
            "user_id": UUID(subject),
            "token": new_refresh,
            "expires_at": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        })

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, token: str, user_id: UUID, request: Request):
        db_token = await self.token_repo.get_by_token(token)
        if db_token:
            await self.token_repo.update(db_token.id, {"is_revoked": True})

        await self.audit_repo.create_log(
            user_id=user_id,
            action=AuditAction.LOGOUT,
            resource_type="user",
            resource_id=str(user_id),
            description="User logged out",
            ip_address=request.client.host if request.client else None,
        )

    async def forgot_password(self, email: str) -> str:
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Return without error to prevent email enumeration
            return "If email exists, a reset link has been sent."

        reset_token = create_password_reset_token(email)
        await self.user_repo.update(user.id, {
            "password_reset_token": reset_token,
            "password_reset_expires": datetime.utcnow() + __import__("datetime").timedelta(hours=24),
        })

        # TODO: Send email via Celery task
        return "Password reset link sent to your email."

    async def reset_password(self, token: str, new_password: str) -> bool:
        email = verify_password_reset_token(token)
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

        user = await self.user_repo.get_by_email(email)
        if not user or user.password_reset_token != token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

        hashed = get_password_hash(new_password)
        await self.user_repo.update(user.id, {
            "hashed_password": hashed,
            "password_reset_token": None,
            "password_reset_expires": None,
        })
        return True
