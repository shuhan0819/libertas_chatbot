from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import threading

from app.database import get_db
from app.limiter import limiter
from app.models import User, Session, Message, DangerEvent, InstitutionSettings
from app.schemas import (
    UserCreate, UserResponse,
    SessionResponse, MessageResponse,
    DangerEventResponse, DangerStatusUpdate
)
from app.auth import hash_password, get_admin_user
from app import kb_state

router = APIRouter(prefix="/admin", tags=["社工後台"])


# ──────────────────────────────────────────
# 知識庫重建
# ──────────────────────────────────────────

def _run_rebuild(gmail_user: str, gmail_password: str, alert_emails: list):
    """在背景執行緒中重建知識庫"""
    try:
        kb_state.set_rebuilding("📥 從 Google Drive 下載文件...", 10)

        import os
        from app.rag.document_loader import load_documents_from_drive
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        if not folder_id:
            kb_state.set_error("未設定 GOOGLE_DRIVE_FOLDER_ID 環境變數")
            return
        documents = load_documents_from_drive("credentials.json", folder_id)

        if not documents:
            kb_state.set_error("找不到任何文件")
            return

        kb_state.set_rebuilding(f"📄 讀取到 {len(documents)} 份文件，生成向量中...", 30)

        from app.rag.knowledge_base import build_knowledge_base
        from app.rag.llm import generate

        total = len(documents)

        def progress_callback(current, total_chunks):
            pct = 30 + int((current / total_chunks) * 60)
            kb_state.set_rebuilding(f"🔄 向量化進度：{current}/{total_chunks}", pct)

        build_knowledge_base(
            documents=documents,
            llm_generate_fn=generate,
            save_dir="knowledge_base",
            progress_callback=progress_callback,
        )

        kb_state.set_rebuilding("🔄 重新載入知識庫...", 95)

        # 重新載入 RAG
        from app.rag import pipeline
        pipeline._index = None
        pipeline._metadata = None
        pipeline._embedder = None
        pipeline.init_rag()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        kb_state.set_done(now)

        # 寄送完成通知
        if gmail_user and alert_emails:
            try:
                from app.email_sender import send_email
                send_email(
                    to=alert_emails,
                    subject="✅ 利伯他茲知識庫重建完成",
                    html=f"""
                    <div style="font-family:sans-serif;padding:20px;">
                        <h3>✅ 知識庫重建完成</h3>
                        <p>完成時間：{now}</p>
                        <p>共讀取 {len(documents)} 份文件。</p>
                    </div>""",
                    gmail_user=gmail_user,
                    gmail_password=gmail_password,
                )
            except Exception as e:
                print(f"⚠️ 完成通知寄送失敗：{e}")

        print("✅ 知識庫重建完成")

    except Exception as e:
        kb_state.set_error(str(e))
        print(f"❌ 知識庫重建失敗：{e}")


@router.post("/rebuild-kb", summary="重建知識庫")
@limiter.limit("5/minute")
async def rebuild_kb(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    if kb_state._read()["is_rebuilding"]:
        raise HTTPException(status_code=400, detail="知識庫正在重建中，請稍後再試")

    # 讀取 Gmail 設定
    result = await db.execute(select(InstitutionSettings))
    inst = result.scalar_one_or_none()
    gmail_user = inst.gmail_user if inst else ""
    gmail_password = inst.gmail_app_password if inst else ""
    alert_emails = [e.strip() for e in (inst.alert_emails or "").split(",") if e.strip()]

    # 在背景執行緒執行（不阻塞 API）
    thread = threading.Thread(
        target=_run_rebuild,
        args=(gmail_user, gmail_password, alert_emails),
        daemon=True,
    )
    thread.start()

    return {"message": "知識庫重建已開始"}


@router.get("/kb-status")
async def get_kb_status(_: User = Depends(get_admin_user)):
    return kb_state._read()


# ──────────────────────────────────────────
# 機構設定
# ──────────────────────────────────────────

class InstitutionSettingsResponse(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    open_hours: Optional[str] = None
    alert_emails: Optional[str] = None
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class InstitutionSettingsUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    open_hours: Optional[str] = None
    alert_emails: Optional[str] = None
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None


@router.get("/institution", response_model=InstitutionSettingsResponse)
async def get_institution(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InstitutionSettings))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = InstitutionSettings(
            name="利伯他茲教育基金會", address="", phone="",
            open_hours="週一至週五 09:00-17:00",
            alert_emails="", gmail_user="", gmail_app_password="",
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return InstitutionSettingsResponse.model_validate(settings)


@router.put("/institution", response_model=InstitutionSettingsResponse)
async def update_institution(
    body: InstitutionSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    result = await db.execute(select(InstitutionSettings))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = InstitutionSettings()
        db.add(settings)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(settings, field, value)

    settings.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(settings)
    return InstitutionSettingsResponse.model_validate(settings)


# ──────────────────────────────────────────
# 帳號管理
# ──────────────────────────────────────────

class ResetPasswordRequest(BaseModel):
    new_password: str


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"帳號 '{body.username}' 已存在")

    new_user = User(
        username=body.username,
        password=hash_password(body.password),
        display_name=body.display_name,
        email=getattr(body, 'email', ''),
        is_admin=body.is_admin,
        is_active=True,
        is_verified=True,  # 社工建立的帳號不需要驗證
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(User).where(User.is_admin == 0).order_by(desc(User.created_at))
    )
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.patch("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="密碼至少需要 6 個字元")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="找不到此使用者")
    user.password = hash_password(body.new_password)
    await db.commit()

    if user.email:
        try:
            inst_result = await db.execute(select(InstitutionSettings))
            inst = inst_result.scalar_one_or_none()
            gmail_user = inst.gmail_user if inst else ""
            gmail_password = inst.gmail_app_password if inst else ""
            if gmail_user and gmail_password:
                from app.email_sender import send_email
                send_email(
                    to=[user.email],
                    subject="【利伯他茲助理】您的帳號密碼已被重設",
                    html=f"""
                    <div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
                        <div style="background:#1a237e;color:white;padding:20px;border-radius:8px 8px 0 0;">
                            <h2 style="margin:0;">利伯他茲助理 - 密碼重設通知</h2>
                        </div>
                        <div style="border:1px solid #e0e0e0;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
                            <p>您好，{user.display_name}！</p>
                            <p>您的帳號密碼已由管理員重設，請使用新密碼重新登入系統。</p>
                            <p style="color:#d32f2f;">如果您沒有要求重設密碼，請立即聯繫您的社工人員。</p>
                        </div>
                    </div>""",
                    gmail_user=gmail_user,
                    gmail_password=gmail_password,
                )
        except Exception as e:
            print(f"⚠️ 密碼重設通知寄送失敗：{e}")

    return {"message": f"帳號 '{user.display_name}' 的密碼已重設"}


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="找不到此使用者")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="找不到此使用者")
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="找不到此使用者")

    display_name = user.display_name
    try:
        sessions_result = await db.execute(select(Session.id).where(Session.user_id == user_id))
        session_ids = [row[0] for row in sessions_result.fetchall()]

        await db.execute(delete(DangerEvent).where(DangerEvent.user_id == user_id))
        if session_ids:
            await db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
        await db.execute(delete(Session).where(Session.user_id == user_id))
        await db.delete(user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="刪除失敗，操作已回滾")
    return {"message": f"帳號 '{display_name}' 及所有相關記錄已永久刪除"}


# ──────────────────────────────────────────
# 對話記錄查詢
# ──────────────────────────────────────────

@router.get("/users/{user_id}/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(Session).where(Session.user_id == user_id).order_by(desc(Session.started_at))
    )
    return [SessionResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return [MessageResponse.model_validate(m) for m in result.scalars().all()]


# ──────────────────────────────────────────
# 危險訊號管理
# ──────────────────────────────────────────

@router.get("/danger-events", response_model=List[DangerEventResponse])
async def get_danger_events(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_admin_user),
):
    result = await db.execute(select(DangerEvent).order_by(desc(DangerEvent.notified_at)))
    return [DangerEventResponse.model_validate(e) for e in result.scalars().all()]


@router.patch("/danger-events/{event_id}/status", response_model=DangerEventResponse)
async def update_danger_status(
    event_id: int, body: DangerStatusUpdate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_admin_user),
):
    result = await db.execute(select(DangerEvent).where(DangerEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="找不到此事件")
    event.status = body.status
    await db.commit()
    await db.refresh(event)
    return DangerEventResponse.model_validate(event)
