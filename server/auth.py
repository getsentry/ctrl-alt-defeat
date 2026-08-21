"""
Authentication and authorization module using JWT tokens
"""

import os
from datetime import timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from utils import utc_now

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 90  # 90 days for guest sessions

# bcrypt hashes the first 72 bytes of a password and refuses anything longer,
# so this is the ceiling, not a policy choice.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 4

# Bearer token scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT token payload"""

    user_id: int
    username: str
    account_type: str = "guest"


class Token(BaseModel):
    """Access token response"""

    access_token: str
    token_type: str = "bearer"


def password_error(password: str) -> Optional[str]:
    """Why `password` cannot be used, or None if it can be.

    The message is shown to the player as it is, so write it for them. The
    rules are deliberately loose: nothing here is worth guarding hard.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"A password needs at least {MIN_PASSWORD_LENGTH} characters."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"A password can be at most {MAX_PASSWORD_BYTES} bytes."
    return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        # A password over the byte limit, or a hash this bcrypt cannot read.
        # Neither can match, and neither is worth a 500.
        return False


def get_password_hash(password: str) -> str:
    """Hash a password.

    Raises ValueError for a password bcrypt will not take. Call
    `password_error` first to tell the player why.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """
    Dependency to get the current user from JWT token

    Usage:
        @app.get("/protected")
        async def protected_route(current_user: TokenData = Depends(get_current_user)):
            return {"user_id": current_user.user_id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id: int = payload.get("user_id")
        username: str = payload.get("username")
        account_type: str = payload.get("account_type", "guest")

        if user_id is None or username is None:
            raise credentials_exception

        token_data = TokenData(
            user_id=user_id, username=username, account_type=account_type
        )
    except JWTError:
        raise credentials_exception

    return token_data


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """
    Optional authentication - returns user if token provided, None otherwise

    Usage:
        @app.get("/public")
        async def public_route(current_user: Optional[TokenData] = Depends(get_optional_user)):
            if current_user:
                return {"message": f"Hello {current_user.username}"}
            return {"message": "Hello anonymous"}
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
