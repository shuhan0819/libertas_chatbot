from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
from app.models import DangerStatus


# ──────────────────────────────────────────
# 帳號相關
# ──────────────────────────────────────────

class UserCreate(BaseModel):
    """社工建立新帳號時使用"""
    username: str
    password: str
    display_name: str
    email: str = ""
    is_admin: int = 0

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("帳號至少需要 3 個字元")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密碼至少需要 6 個字元")
        return v


class RegisterRequest(BaseModel):
    """使用者自行註冊"""
    username: str
    password: str
    display_name: str
    email: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("帳號至少需要 3 個字元")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密碼至少需要 6 個字元")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("請輸入有效的 Email")
        return v


class UserResponse(BaseModel):
    """回傳給前端的使用者資訊（不含密碼）"""
    id: int
    username: str
    display_name: str
    email: Optional[str] = None
    is_admin: int
    is_active: Optional[bool] = True
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────
# 登入相關
# ──────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ──────────────────────────────────────────
# Session 相關
# ──────────────────────────────────────────

class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    user_id: int
    started_at: datetime
    title: Optional[str]

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────
# 訊息相關
# ──────────────────────────────────────────

class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    audio_url: Optional[str]
    audio_filename: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────
# 危險訊號相關
# ──────────────────────────────────────────

class DangerEventResponse(BaseModel):
    id: int
    user_id: int
    session_id: int
    triggered_keyword: Optional[str]
    full_conversation: Optional[str]
    notified_at: datetime
    level: Optional[str] = "notice"
    status: DangerStatus

    model_config = {"from_attributes": True}


class DangerStatusUpdate(BaseModel):
    status: DangerStatus

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密碼至少需要 6 個字元")
        return v
