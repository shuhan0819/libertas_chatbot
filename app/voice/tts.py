import edge_tts
import tempfile
import os

VOICE = "zh-TW-HsiaoChenNeural"


async def text_to_speech(text: str) -> bytes:
    """將文字轉成語音，回傳 mp3 bytes"""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)