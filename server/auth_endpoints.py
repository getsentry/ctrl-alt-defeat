"""
Authentication endpoints for user login/registration
"""

import random
from typing import Optional

from auth import (
    Token,
    TokenData,
    create_access_token,
    get_current_user,
    get_password_hash,
    password_error,
    verify_password,
)
from database import db_manager
from fastapi import APIRouter, Depends, HTTPException, status
from models import User
from name_generator import name_error, name_with_suffix, random_name
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from utils import utc_now

router = APIRouter(prefix="/auth", tags=["authentication"])

# How many names to propose before giving up. The first few are plain
# combinations; after that a number is added, because the plain combinations
# may all be taken.
PLAIN_NAME_ATTEMPTS = 5
TOTAL_NAME_ATTEMPTS = 20


class LoginRequest(BaseModel):
    """Login with username and password"""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Register a new user account"""

    username: str
    password: str
    email: Optional[str] = None  # Just use str, not EmailStr to avoid dependency


class ChangeNameRequest(BaseModel):
    """Change the name on the signed-in account"""

    name: str


class GuestLoginResponse(BaseModel):
    """Response for guest login"""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


async def name_is_taken(db, name: str, except_user_id: Optional[int] = None) -> bool:
    """Whether another account already holds `name`, ignoring letter case."""
    query = select(User.id).where(func.lower(User.username) == name.lower())
    if except_user_id is not None:
        query = query.where(User.id != except_user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


def new_guest(name: str) -> User:
    """A guest account row under `name`. Not yet saved."""
    return User(
        username=name,
        account_type="guest",
        account_status="active",
        total_games_played=0,
        total_wins=0,
        total_losses=0,
        current_rank=1000,
    )


async def insert_generated_guest(db) -> User:
    """Save a guest account under a free generated name.

    Two players can be given the same name at the same moment, and only the
    database can settle that, so a rejected insert is retried rather than
    prevented.
    """
    for attempt in range(TOTAL_NAME_ATTEMPTS):
        name = random_name()
        if attempt >= PLAIN_NAME_ATTEMPTS:
            name = name_with_suffix(name, random.randint(10, 9999))

        user = new_guest(name)
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(user)
        return user

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not find a free name. Try again.",
    )


def _token_for(user: User) -> str:
    return create_access_token(
        data={
            "user_id": user.id,
            "username": user.username,
            "account_type": user.account_type,
        }
    )


@router.post("/guest", response_model=GuestLoginResponse)
async def create_guest_session():
    """
    Create a guest account and return an access token
    No password required - instant play

    The player does not name themselves here. Nothing stands between them and
    the first game, so the server names the account, and the player may change
    it later through `POST /auth/name`.
    """
    async with db_manager.get_session() as db:
        user = await insert_generated_guest(db)
        return GuestLoginResponse(
            access_token=_token_for(user), user_id=user.id, username=user.username
        )


@router.post("/register", response_model=Token)
async def register(request: RegisterRequest):
    """
    Register a new user account with username and password
    """
    problem = name_error(request.username) or password_error(request.password)
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)

    async with db_manager.get_session() as db:
        # Check if username already exists
        if await name_is_taken(db, request.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That name is taken.",
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

        return Token(access_token=_token_for(user))


@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    """
    Login with username and password
    """
    async with db_manager.get_session() as db:
        # Find user by name. Letter case does not matter, because the name a
        # player types is the name they read off the screen.
        result = await db.execute(
            select(User).where(func.lower(User.username) == request.username.lower())
        )
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
        user.last_login_at = utc_now()
        await db.commit()

        return Token(access_token=_token_for(user))


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
            "account_type": user.account_type,
            "total_games": user.total_games_played,
            "wins": user.total_wins,
            "losses": user.total_losses,
            "rank": user.current_rank,
            "snuba_coin": user.snuba_coin,
        }


@router.post("/name")
async def change_name(
    request: ChangeNameRequest, current_user: TokenData = Depends(get_current_user)
):
    """
    Change the name on the signed-in account

    The name is the account's identity, so a new token is issued with it.
    """
    name = request.name.strip()
    problem = name_error(name)
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)

    async with db_manager.get_session() as db:
        result = await db.execute(select(User).where(User.id == current_user.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if await name_is_taken(db, name, except_user_id=user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="That name is taken."
            )

        user.username = name
        try:
            await db.commit()
        except IntegrityError:
            # Another player claimed the name between the check and the write.
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="That name is taken."
            )
        await db.refresh(user)

        return {"username": user.username, "access_token": _token_for(user)}


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

    problem = name_error(request.username) or password_error(request.password)
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)

    async with db_manager.get_session() as db:
        # Get the user
        result = await db.execute(select(User).where(User.id == current_user.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if new username is available
        if await name_is_taken(db, request.username, except_user_id=user.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That name is taken.",
            )

        # Update user to registered account
        user.username = request.username
        user.email = request.email
        user.password_hash = get_password_hash(request.password)
        user.account_type = "registered"

        await db.commit()
        await db.refresh(user)

        return Token(access_token=_token_for(user))
