"""Pydantic schemas for authentication endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

LearningGoal = Literal["exam", "work", "study", "daily_life", "family", "other"]


class RegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    cefr_level: Optional[str] = Field(
        None,
        pattern=r"^(A0|A1|A2|B1|B2|C1|C2)$",
        description="CEFR level: A0–C2",
    )
    timezone: Optional[str] = Field(None, max_length=64, description="IANA name, e.g. Africa/Lagos")
    learning_goal: Optional[LearningGoal] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ResetPasswordRequestBody(BaseModel):
    email: EmailStr


class ResetPasswordConfirmBody(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, description="Minimum 8 characters")


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    cefr_level: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
