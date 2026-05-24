import os
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.auth import get_current_user
from app.models import User
from fastapi import Depends, HTTPException

# 音檔存放資料夾
AUDIO_DIR = "audio_files"
os.makedirs(AUDIO_DIR, exist_ok=True)


def save_audio(
    audio_bytes: bytes,
    user_id: int,
    session_id: int,
    mime_type: str = "audio/mpeg"
) -> tuple[str, str]:
    """
    儲存音檔到本地資料夾
    回傳：(檔案名稱, 存取路徑)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "mp3" if "mpeg" in mime_type else "wav"
    filename = f"user{user_id}_sess{session_id}_{timestamp}.{ext}"
    filepath = os.path.join(AUDIO_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    # 回傳存取 URL（透過 API endpoint 下載）
    audio_url = f"/api/chat/audio/{filename}"
    return filename, audio_url


# ──────────────────────────────────────────
# 音檔下載 endpoint（加入 chat router）
# ──────────────────────────────────────────

audio_router = APIRouter()


@audio_router.get("/audio/{filename}", summary="下載音檔")
async def get_audio(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """
    讓社工或使用者下載音檔
    需要登入才能存取
    """
    # 防止路徑穿越攻擊
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="無效的檔案名稱")

    filepath = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="找不到此音檔")

    media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
    return FileResponse(filepath, media_type=media_type, filename=filename)
