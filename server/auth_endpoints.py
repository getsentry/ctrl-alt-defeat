"""
Authentication endpoints for user login/registration
"""

import random
import uuid
from datetime import datetime
from typing import Optional

from auth import (
    Token,
    TokenData,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from database import db_manager
from fastapi import APIRouter, Depends, HTTPException, status
from models import User
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    """Login with username and password"""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Register a new user account"""

    username: str
    password: str
    email: Optional[str] = None  # Just use str, not EmailStr to avoid dependency
    display_name: Optional[str] = None


class GuestLoginResponse(BaseModel):
    """Response for guest login"""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


@router.post("/guest", response_model=GuestLoginResponse)
async def create_guest_session():
    """
    Create a guest account and return an access token
    No password required - instant play
    """
    async with db_manager.get_session() as db:
        # Generate unique guest username
        guest_id = uuid.uuid4().hex[:8]
        username = f"Guest_{guest_id}_{random.randint(1000, 9999)}"

        # Create guest user
        user = User(
            username=username,
            display_name=f"Player_{guest_id}",
            account_type="guest",
            account_status="active",
            total_games_played=0,
            total_wins=0,
            total_losses=0,
            current_rank=1000,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create access token
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "username": user.username,
                "account_type": "guest",
            }
        )

        return GuestLoginResponse(
            access_token=access_token, user_id=user.id, username=user.username
        )


@router.post("/register", response_model=Token)
async def register(request: RegisterRequest):
    """
    Register a new user account with username and password
    """
    async with db_manager.get_session() as db:
        # Check if username already exists
        result = await db.execute(select(User).where(User.username == request.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

        # Check if email already exists (if provided)
        if request.email:
            result = await db.execute(select(User).where(User.email == request.email))
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        # Create new user
        user = User(
            username=request.username,
            display_name=request.display_name or request.username,
            email=request.email,
            password_hash=get_password_hash(request.password),
            account_type="registered",
            account_status="active",
            total_games_played=0,
            total_wins=0,
            total_losses=0,
            current_rank=1000,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create access token
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "username": user.username,
                "account_type": "registered",
            }
        )

        return Token(access_token=access_token)


@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    """
    Login with username and password
    """
    async with db_manager.get_session() as db:
        # Find user by username
        result = await db.execute(select(User).where(User.username == request.username))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        # Check if user has a password (registered account)
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This is a guest account. Please register to set a password.",
            )

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        # Update last login
        user.last_login_at = datetime.utcnow()
        await db.commit()

        # Create access token
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "username": user.username,
                "account_type": user.account_type,
            }
        )

        return Token(access_token=access_token)


@router.get("/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """
    Get current user information from token
    """
    async with db_manager.get_session() as db:
        result = await db.execute(select(User).where(User.id == current_user.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "account_type": user.account_type,
            "total_games": user.total_games_played,
            "wins": user.total_wins,
            "losses": user.total_losses,
            "rank": user.current_rank,
        }


@router.post("/upgrade-guest")
async def upgrade_guest_account(
    request: RegisterRequest, current_user: TokenData = Depends(get_current_user)
):
    """
    Upgrade a guest account to a registered account
    """
    if current_user.account_type != "guest":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already registered",
        )

    async with db_manager.get_session() as db:
        # Get the user
        result = await db.execute(select(User).where(User.id == current_user.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if new username is available
        if request.username != user.username:
            result = await db.execute(
                select(User).where(User.username == request.username)
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        # Update user to registered account
        user.username = request.username
        user.display_name = request.display_name or request.username
        user.email = request.email
        user.password_hash = get_password_hash(request.password)
        user.account_type = "registered"

        await db.commit()

        # Create new access token with updated info
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "username": user.username,
                "account_type": "registered",
            }
        )

        return Token(access_token=access_token)
