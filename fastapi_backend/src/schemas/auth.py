from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address (unique).")
    password: str = Field(..., min_length=8, description="User password (min 8 chars).")
    display_name: str | None = Field(None, description="Optional display name.")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email.")
    password: str = Field(..., description="User password.")


class TokenPair(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    refresh_token: str = Field(..., description="JWT refresh token.")
    token_type: str = Field("bearer", description="Token type (bearer).")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token.")


class UserPublic(BaseModel):
    id: UUID = Field(..., description="User ID.")
    email: EmailStr = Field(..., description="User email.")
    display_name: str | None = Field(None, description="Display name.")
    is_active: bool = Field(..., description="Whether the user is active.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Update timestamp.")
