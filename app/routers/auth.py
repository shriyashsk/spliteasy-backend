from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
import httpx

from app.database import get_db
from app.models.models import User, Session
from app.services.auth_service import hash_password, verify_password, create_session, revoke_session, generate_token
from app.services.invite_service import send_password_reset_email
from app.middleware.auth_middleware import get_current_user
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/signup")
async def signup(body: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, detail={"code": "EMAIL_TAKEN", "message": "Email already registered"})

    user = User(
        full_name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = await create_session(db, user.id, request.headers.get("user-agent"), request.client.host if request.client else None)
    return {"success": True, "data": {"token": token, "user": {"id": user.id, "full_name": user.full_name, "email": user.email}}}


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"})

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = await create_session(db, user.id, request.headers.get("user-agent"), request.client.host if request.client else None)
    return {"success": True, "data": {"token": token, "user": {"id": user.id, "full_name": user.full_name, "email": user.email}}}


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        await revoke_session(db, auth.split(" ")[1])
    return {"success": True, "data": {"message": "Logged out"}}


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    return {"success": True, "data": {"id": user.id, "full_name": user.full_name, "email": user.email,
                                       "preferred_currency": user.preferred_currency, "avatar_url": user.avatar_url}}


@router.get("/google")
async def google_login():
    params = (
        f"client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.BACKEND_URL}/auth/google/callback"
        f"&response_type=code&scope=openid%20email%20profile&access_type=offline"
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{settings.BACKEND_URL}/auth/google/callback",
            "grant_type": "authorization_code",
        })
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(400, "Google OAuth failed")

        user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                     headers={"Authorization": f"Bearer {access_token}"})
        google_user = user_resp.json()

    google_id = google_user["id"]
    email = google_user["email"]
    name = google_user.get("name", email)

    result = await db.execute(select(User).where(User.oauth_provider_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user:
        user = User(full_name=name, email=email, auth_provider="google",
                    oauth_provider_id=google_id, email_verified=True,
                    avatar_url=google_user.get("picture"))
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.oauth_provider_id = google_id
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

    session_token = await create_session(db, user.id, request.headers.get("user-agent"), request.client.host if request.client else None)
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={session_token}")


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
        token = generate_token(48)
        reset_session = Session(
            session_id=f"reset_{token}",
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset_session)
        await db.commit()
        try:
            send_password_reset_email(user.email, token)
        except Exception:
            pass
    return {"success": True, "data": {"message": "If that email exists, a reset link was sent"}}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    session_id = f"reset_{body.token}"
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(400, detail={"code": "INVALID_TOKEN", "message": "Invalid or expired reset token"})

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    user.password_hash = hash_password(body.new_password)
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "data": {"message": "Password reset successful"}}


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user.password_hash or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, detail={"code": "WRONG_PASSWORD", "message": "Current password incorrect"})
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"success": True, "data": {"message": "Password changed"}}