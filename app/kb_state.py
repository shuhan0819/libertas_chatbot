"""
知識庫重建狀態追蹤（使用 JSON 檔案，避免 --reload 模式下記憶體重置）
"""
import json
import os

STATE_FILE = "kb_state.json"

_DEFAULT = {
    "is_rebuilding": False,
    "progress": 0,
    "stage": "",
    "last_rebuilt": None,
    "error": None,
}


def _read() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT.copy()


def _write(data: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# 讓 admin.py 直接讀 kb_status（向下相容）
class _KBStatus:
    @property
    def kb_status(self):
        return _read()


kb_status_obj = _KBStatus()


def set_rebuilding(stage: str, progress: int):
    data = _read()
    data["is_rebuilding"] = True
    data["stage"] = stage
    data["progress"] = progress
    data["error"] = None
    _write(data)


def set_done(timestamp: str):
    _write({
        "is_rebuilding": False,
        "progress": 100,
        "stage": "重建完成",
        "last_rebuilt": timestamp,
        "error": None,
    })


def set_error(msg: str):
    data = _read()
    data["is_rebuilding"] = False
    data["progress"] = 0
    data["stage"] = "重建失敗"
    data["error"] = msg
    _write(data)
