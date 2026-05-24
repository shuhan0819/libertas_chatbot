import json
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.database import get_db
from app.limiter import limiter
from app.models import User, Session, Message, DangerEvent, DangerStatus
from app.schemas import SessionCreate, SessionResponse, MessageResponse
from app.auth import get_current_user
from app.voice.audio_storage import audio_router, save_audio
from pydantic import BaseModel

MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/wav", "audio/mp4"}

router = APIRouter(prefix="/chat", tags=["聊天"])
router.include_router(audio_router)

# ──────────────────────────────────────────
# 危機回覆底線（crisis 等級使用）
# AI 會以此為基礎自然融入，避免純固定語句
# ──────────────────────────────────────────
CRISIS_BASE_RESPONSE = """我聽到你說的話，我很擔心你現在的狀況。

你願意說出來，這本身已經很不容易了。你不需要一個人扛著這些。

請立即聯繫你的社工人員，或撥打以下專線：
• 自殺防治專線：1925（24小時）
• 張老師專線：1980
• 生命線：1995

我已通知相關社工人員，他們會盡快與你聯繫。"""


def generate_crisis_reply(user_message: str, chat_history: list) -> str:
    """
    crisis 等級：以底線為基礎，由 AI 自然融入當下語境生成回覆
    """
    try:
        from app.rag.llm import client, MODEL
        system = f"""你是利伯他茲教育基金會的社工支持助理。
使用者正處於危機狀態，請根據以下底線回覆框架，結合使用者的當下語境，生成一段溫暖、不生硬的回覆。

【底線框架（必須包含以下要素，但可以自然調整語氣）】
{CRISIS_BASE_RESPONSE}

要求：
- 開頭先回應使用者說的話，讓對方感受到被聽見
- 保留緊急專線資訊，不可省略
- 語氣要溫暖、穩定，避免過於公式化
- 使用繁體中文，150字以內"""

        messages = [{"role": "system", "content": system}]
        if chat_history:
            for msg in chat_history[-4:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return CRISIS_BASE_RESPONSE


def generate_concern_reply(user_message: str, chat_history: list) -> str:
    """
    concern 等級：同理回覆 + 自然帶入資源
    """
    try:
        from app.rag.llm import client, MODEL
        system = """你是利伯他茲教育基金會的社工支持助理。
使用者表達了可能的自我傷害意圖或強烈負面情緒，請給予同理與支持的回覆。

要求：
- 先同理使用者的感受，讓對方感受到被理解
- 不評價、不說教
- 適度自然帶入協助資源（安心專線1925、生命線1995）
- 語氣溫暖，不要過於制式化
- 使用繁體中文，150字以內"""

        messages = [{"role": "system", "content": system}]
        if chat_history:
            for msg in chat_history[-4:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "我聽到你了，你說的這些讓我很在意。如果你需要有人陪你說說話，可以撥打安心專線 1925（24小時）。"


@router.post("/sessions", response_model=SessionResponse, summary="開啟新的對話 session")
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime
    title = body.title or datetime.now().strftime("%Y-%m-%d %H:%M 的對話")
    new_session = Session(user_id=current_user.id, title=title)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return SessionResponse.model_validate(new_session)


@router.get("/sessions", response_model=List[SessionResponse])
async def get_my_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Session)
        .where(
            Session.user_id == current_user.id,
            Session.is_deleted == False,
        )
        .order_by(desc(Session.started_at))
    )
    return [SessionResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="找不到此對話")

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return [MessageResponse.model_validate(m) for m in result.scalars().all()]


# ──────────────────────────────────────────
# 共用：處理訊息邏輯
# ──────────────────────────────────────────

async def _process_message(
    session_id: int,
    user_message: str,
    current_user: User,
    db: AsyncSession,
    audio_url: str = None,
    audio_filename: str = None,
) -> dict:
    # 取得對話歷史
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(desc(Message.created_at))
        .limit(6)
    )
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_result.scalars().all())
    ]

    # 儲存使用者訊息
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=user_message,
        audio_url=audio_url,
        audio_filename=audio_filename,
    )
    db.add(user_msg)
    await db.flush()

    # ── 危險訊號偵測 ──
    danger_info = {
        "level": "safe",
        "keyword": "",
        "intent": "knowledge",
        "risk_level": 0,
        "need_notification": False,
        "confidence": 1.0,
        "reason": "",
    }

    try:
        from app.danger.detector import check_danger
        danger_info = check_danger(user_message)
        print(f"🔍 危險偵測結果：{danger_info}")
    except Exception as e:
        print(f"⚠️ 危險偵測失敗：{e}")

    level = danger_info.get("level", "safe")

    # ── 決策引擎 ──
    used_rag = False

    if level == "crisis":
        # 立即危機：AI 融入底線回覆 + 記錄 + 寄 email
        reply_text = generate_crisis_reply(user_message, chat_history)
        _save_danger_event(db, current_user, session_id, danger_info, chat_history, user_message)
        await _send_notification(db, current_user, danger_info, chat_history, user_message)

    elif level == "concern":
        # 高關注：AI 同理回覆 + 記錄 + 寄 email
        reply_text = generate_concern_reply(user_message, chat_history)
        _save_danger_event(db, current_user, session_id, danger_info, chat_history, user_message)
        await _send_notification(db, current_user, danger_info, chat_history, user_message)

    elif level == "notice":
        # 留意：正常 RAG 回覆 + 後台記錄，不寄 email
        try:
            from app.rag.pipeline import rag_chat
            rag_result = rag_chat(user_message=user_message, chat_history=chat_history)
            reply_text = rag_result["reply"]
            used_rag = rag_result["used_rag"]
        except Exception as e:
            reply_text = "系統發生錯誤，請稍後再試。"
        _save_danger_event(db, current_user, session_id, danger_info, chat_history, user_message)

    else:
        # safe：正常 RAG 回覆
        try:
            from app.rag.pipeline import rag_chat
            rag_result = rag_chat(user_message=user_message, chat_history=chat_history)
            reply_text = rag_result["reply"]
            used_rag = rag_result["used_rag"]
        except Exception as e:
            reply_text = "系統發生錯誤，請稍後再試。"

    # 儲存助理回覆
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return {
        "user_msg": user_msg,
        "assistant_msg": assistant_msg,
        "is_danger": level in ("crisis", "concern"),
        "used_rag": used_rag,
    }


def _save_danger_event(db, current_user, session_id, danger_info, chat_history, user_message):
    """儲存危險事件到後台"""
    try:
        level = danger_info.get("level", "notice")
        # 對應新等級到資料庫的 DangerStatus
        status_map = {
            "crisis": DangerStatus.pending,
            "concern": DangerStatus.pending,
            "notice": DangerStatus.pending,
        }
        danger_event = DangerEvent(
            user_id=current_user.id,
            session_id=session_id,
            triggered_keyword=danger_info.get("keyword", ""),
            full_conversation=json.dumps(chat_history + [{"role": "user", "content": user_message}], ensure_ascii=False),
            level=danger_info.get("level", "notice"),
            status=status_map.get(level, DangerStatus.pending),
        )
        db.add(danger_event)
    except Exception as e:
        print(f"⚠️ 危險事件儲存失敗：{e}")


async def _send_notification(db, current_user, danger_info, chat_history, user_message):
    """寄送 email 通報（crisis 和 concern 才呼叫）"""
    try:
        from app.danger.notifier import send_danger_alert
        from app.models import InstitutionSettings
        from sqlalchemy import select

        inst_result = await db.execute(select(InstitutionSettings))
        inst = inst_result.scalar_one_or_none()

        db_recipients = None
        db_gmail_user = None
        db_gmail_password = None

        if inst:
            if inst.alert_emails:
                db_recipients = [e.strip() for e in inst.alert_emails.split(',') if e.strip()]
            if inst.gmail_user:
                db_gmail_user = inst.gmail_user
            if inst.gmail_app_password:
                db_gmail_password = inst.gmail_app_password

        conv_list = chat_history + [{"role": "user", "content": user_message}]
        send_danger_alert(
            user_display_name=current_user.display_name,
            username=current_user.username,
            danger_info=danger_info,
            full_conversation=conv_list,
            recipients=db_recipients,
            gmail_user=db_gmail_user,
            gmail_password=db_gmail_password,
        )
    except Exception as e:
        print(f"⚠️ 通報失敗：{e}")


# ──────────────────────────────────────────
# 文字聊天
# ──────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: int
    message: str


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    is_danger: bool = False
    used_rag: bool = False


@router.post("/send", response_model=ChatResponse, summary="傳送文字訊息")
async def send_message(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app import kb_state
    if kb_state._read()["is_rebuilding"]:
        raise HTTPException(status_code=503, detail="系統正在更新知識庫，請稍候幾分鐘後再試。")

    result = await db.execute(
        select(Session).where(
            Session.id == body.session_id,
            Session.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="找不到此對話")

    result = await _process_message(
        session_id=body.session_id,
        user_message=body.message,
        current_user=current_user,
        db=db,
    )

    return ChatResponse(
        user_message=MessageResponse.model_validate(result["user_msg"]),
        assistant_message=MessageResponse.model_validate(result["assistant_msg"]),
        is_danger=result["is_danger"],
        used_rag=result["used_rag"],
    )


# ──────────────────────────────────────────
# 語音聊天
# ──────────────────────────────────────────

class VoiceChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    transcribed_text: str
    is_danger: bool = False
    used_rag: bool = False


@router.post("/voice", response_model=VoiceChatResponse, summary="傳送語音訊息")
@limiter.limit("20/minute")
async def send_voice_message(
    request: Request,
    session_id: int = Form(...),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="找不到此對話")

    content_type = audio.content_type or ""
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail=f"不支援的音訊格式：{content_type}，請使用 WebM、OGG、WAV 或 MP4")

    audio_bytes = await audio.read()

    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="音檔大小超過限制（最大 10MB）")

    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        from app.voice.stt import transcribe

        _executor = ThreadPoolExecutor(max_workers=2)
        loop = asyncio.get_event_loop()
        transcribed_text = await loop.run_in_executor(
            _executor, transcribe, audio_bytes, audio.filename or "audio.wav"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"語音轉文字失敗：{str(e)}")

    if not transcribed_text:
        raise HTTPException(status_code=400, detail="無法辨識語音內容")

    audio_url, audio_filename = None, None
    try:
        audio_filename, audio_url = save_audio(
            audio_bytes=audio_bytes,
            user_id=current_user.id,
            session_id=session_id,
            mime_type=audio.content_type or "audio/wav"
        )
    except Exception as e:
        print(f"⚠️ 音檔儲存失敗：{e}")

    result = await _process_message(
        session_id=session_id,
        user_message=transcribed_text,
        current_user=current_user,
        db=db,
        audio_url=audio_url,
        audio_filename=audio_filename,
    )

    return VoiceChatResponse(
        user_message=MessageResponse.model_validate(result["user_msg"]),
        assistant_message=MessageResponse.model_validate(result["assistant_msg"]),
        transcribed_text=transcribed_text,
        is_danger=result["is_danger"],
        used_rag=result["used_rag"],
    )


@router.get("/tts", summary="文字轉語音")
async def get_tts(
    text: str,
    current_user: User = Depends(get_current_user),
):
    try:
        from app.voice.tts import text_to_speech
        audio_bytes = await text_to_speech(text)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=reply.mp3"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"語音合成失敗：{str(e)}")


class TitleUpdate(BaseModel):
    title: str


@router.patch("/sessions/{session_id}/title", summary="修改對話標題")
async def update_session_title(
    session_id: int,
    body: TitleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="找不到此對話")
    session.title = body.title
    await db.commit()
    return {"message": "標題已更新"}


@router.delete("/sessions/{session_id}", summary="刪除對話（使用者端）")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="找不到此對話")
    session.is_deleted = True
    await db.commit()
    return {"message": "對話已刪除"}