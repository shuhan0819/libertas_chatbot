from sqlalchemy import (
    Column, Integer, String, DateTime,
    ForeignKey, Text, Enum as SAEnum, Boolean
)
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
import enum


class Base(DeclarativeBase):
    pass


class DangerStatus(str, enum.Enum):
    pending = "未處理"
    resolved = "已處理"


class User(Base):
    __tablename__ = "users"

    id                = Column(Integer, primary_key=True, index=True)
    username          = Column(String(50), unique=True, index=True, nullable=False)
    password          = Column(String(255), nullable=False)
    display_name      = Column(String(100), nullable=False)
    email             = Column(String(200), nullable=True)
    is_admin          = Column(Integer, default=0)
    is_active         = Column(Boolean, default=True)
    is_verified           = Column(Boolean, default=False)
    verify_token          = Column(String(100), nullable=True)
    verify_token_expires  = Column(DateTime, nullable=True)
    created_at            = Column(DateTime, default=datetime.utcnow)

    sessions      = relationship("Session", back_populates="user")
    danger_events = relationship("DangerEvent", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    title      = Column(String(200), nullable=True)
    is_deleted = Column(Boolean, default=False)

    user          = relationship("User", back_populates="sessions")
    messages      = relationship("Message", back_populates="session")
    danger_events = relationship("DangerEvent", back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id             = Column(Integer, primary_key=True, index=True)
    session_id     = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role           = Column(String(20), nullable=False)
    content        = Column(Text, nullable=False)
    audio_url      = Column(String(500), nullable=True)
    audio_filename = Column(String(200), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")


class DangerEvent(Base):
    __tablename__ = "danger_events"

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id        = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    triggered_keyword = Column(String(100), nullable=True)
    full_conversation = Column(Text, nullable=True)
    notified_at       = Column(DateTime, default=datetime.utcnow)
    level             = Column(String(20), default="notice", nullable=True)
    status            = Column(SAEnum(DangerStatus), default=DangerStatus.pending, nullable=False)

    user    = relationship("User", back_populates="danger_events")
    session = relationship("Session", back_populates="danger_events")


class InstitutionSettings(Base):
    __tablename__ = "institution_settings"

    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String(200), default="利伯他茲教育基金會")
    address            = Column(String(500), nullable=True)
    phone              = Column(String(50), nullable=True)
    open_hours         = Column(String(200), nullable=True)
    alert_emails       = Column(String(1000), nullable=True)
    gmail_user         = Column(String(200), nullable=True)
    gmail_app_password = Column(String(200), nullable=True)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
