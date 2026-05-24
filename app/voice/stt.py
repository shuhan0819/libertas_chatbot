import whisper
import tempfile
import os
import traceback

_model = whisper.load_model("base")

def get_model():
    global _model
    if _model is None:
        print("🔄 載入 Whisper 模型...")
        _model = whisper.load_model("base")
        print("✅ Whisper 載入完成")
    return _model

def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    model = get_model()
    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        result = model.transcribe(
            tmp_path,
            language="zh",
            initial_prompt="以下是繁體中文對話內容："
        )
        text = result["text"].strip()
        print(f"📁 音檔大小: {len(audio_bytes)} bytes", flush=True)
        print(f"🎤 Whisper 辨識結果: {repr(text)}", flush=True)
        return text
    except Exception as e:
        print(f"❌ Whisper 錯誤: {e}", flush=True)
        traceback.print_exc()
        return ""
    finally:
        os.unlink(tmp_path)
