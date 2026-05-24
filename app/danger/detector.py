from openai import OpenAI
from thefuzz import fuzz
import json
import os

client = OpenAI(
    api_key=os.getenv("LOCAL_LLM_API_KEY", "local"),
    base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8080/v1")
)

MODEL = "qwen2.5-7b-instruct-q4_k_m"

# ──────────────────────────────────────────
# 最高危關鍵字（直接觸發，跳過 LLM 判斷）
# ──────────────────────────────────────────
CRITICAL_KEYWORDS = [
    "遺書", "遺言", "後事", "割腕", "頸動脈", "放血",
    "上吊", "懸掛", "跳樓", "墜樓", "跳橋", "跳河", "跳海",
    "燒炭", "一氧化碳中毒", "農藥自殺", "巴拉刈", "吞藥死", "喝藥死",
    "自裁", "爆頭自殺", "不想活了", "活不下去", "了結生命",
    "結束生命", "終結自己", "去死算了", "想去死",
]

# ──────────────────────────────────────────
# 需要 LLM 進一步判斷的關鍵字
# ──────────────────────────────────────────
SENSITIVE_KEYWORDS = [
    # 自傷意圖
    "傷害自己", "自傷", "割傷自己", "想用刀", "刀傷自",
    "自殘", "刺入", "劃開",
    # 毒品使用意圖
    "想用安非他命", "想用冰毒", "想用K他命", "想吸毒",
    "去買毒", "買毒品", "要用藥", "再用一次",
    "癮頭發作", "毒癮", "買安", "買冰", "打K",
    # 情緒與絕望
    "解脫", "永眠", "長眠", "消失", "人間蒸發",
    "別找我", "沒有我更好", "活著幹嘛",
    "沒救了", "死路一條", "撐不住", "崩潰",
    # 暴力意圖
    "殺了你", "一起死", "同歸於盡", "血債血償",
    # 酒精失控
    "酒精中毒", "喝死", "工業酒精", "甲醇",
    # 戒斷危機
    "生不如死", "快瘋了", "蟲在爬", "幻聽", "幻覺",
    # 網路隱語
    "藍鯨", "登出人生",
    # 常見錯字
    "安非它命", "安非她命", "愷他銘", "K他明", "K他銘",
    "海洛茵", "燒碳", "割碗", "跳摟",
    # 毒品名稱（知識性問答，交 LLM 判斷）
    "安非他命", "冰毒", "K他命", "愷他命", "大麻",
    "海洛因", "可卡因", "古柯鹼", "搖頭丸", "MDMA",
    "毒品", "吸毒", "用藥", "藥頭", "藥販",
    "咖啡包", "毒咖啡", "小惡魔", "彩虹菸", "依託咪酯",
    "喪屍菸彈", "太空煙彈",
    "ice", "meth", "weed", "heroin", "cocaine", "mdma", "lsd",
]

FUZZY_THRESHOLD_CRITICAL = 82
FUZZY_THRESHOLD_SENSITIVE = 80

INTENT_ZH = {
    "knowledge": "知識查詢",
    "emotional_distress": "情緒困擾",
    "self_harm_intent": "自我傷害意圖",
    "violence_intent": "暴力意圖",
    "ambiguous": "語意不明",
}


def _get_segments(text: str, length: int) -> list:
    return [text[i:i+length] for i in range(len(text) - length + 1)]


def keyword_flag(text: str) -> tuple:
    """
    初步關鍵字標記，回傳 (是否為 critical, 觸發關鍵字)
    """
    text_lower = text.lower()

    # 最高危關鍵字：直接標記 critical
    for kw in CRITICAL_KEYWORDS:
        if kw in text:
            return "critical", kw
        if len(kw) >= 2:
            for seg in _get_segments(text, len(kw)):
                if fuzz.ratio(seg, kw) >= FUZZY_THRESHOLD_CRITICAL:
                    return "critical", kw

    # 敏感關鍵字：標記需要 LLM 判斷
    for kw in SENSITIVE_KEYWORDS:
        if kw in text or kw.lower() in text_lower:
            return "sensitive", kw
        if len(kw) >= 3:
            for seg in _get_segments(text, len(kw)):
                if fuzz.ratio(seg, kw) >= FUZZY_THRESHOLD_SENSITIVE:
                    return "sensitive", kw

    return "none", ""


def llm_classify(text: str, flagged_keyword: str = "") -> dict:
    """
    使用 LLM 進行語意分類，回傳結構化 JSON
    """
    system_prompt = """你是一個部署於社工支持系統中的語意風險分析模型，你的任務是分析使用者輸入內容，判斷其中是否包含自我傷害、他人傷害、藥物濫用或心理危機相關風險，並輸出結構化 JSON 結果。

你必須基於語意理解進行判斷，而非單純依賴關鍵字。關鍵字僅能作為輔助線索，但不能單獨決定結果。

在分析時，你需要同時辨識使用者的意圖類型與風險程度。意圖可能包含知識查詢、情緒困擾、自我傷害意圖、暴力意圖或語意不明等情境。你需要判斷這些內容是否涉及實際危險，而不是單純討論相關主題。

如果內容描述已具體化的危險行為，例如明確的自我傷害方式、正在進行的行動、遺書內容或即將執行的計畫，應判定為最高風險（risk_level=3）。

如果內容顯示強烈負面情緒或自我傷害意圖，但未具體化為行動，應判定為高風險（risk_level=2）。

如果內容僅為情緒表達、模糊負面語句，或對敏感議題的知識性詢問（例如毒品種類、自殺後果、法律資訊等），則不應視為危機事件，應歸類為低關注（risk_level=1）或無風險（risk_level=0）。

請輸出以下 JSON 格式，不要輸出任何額外文字：
{
  "intent": "knowledge | emotional_distress | self_harm_intent | violence_intent | ambiguous",
  "risk_level": 0,
  "need_emergency_action": false,
  "need_notification": false,
  "confidence": 0.0,
  "reason": "簡短判斷理由"
}"""

    user_prompt = f"使用者訊息：{text}"
    if flagged_keyword:
        user_prompt += f"\n\n（系統提示：此訊息包含敏感關鍵字「{flagged_keyword}」，請特別留意語意）"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0,
            timeout=30,
        )
        raw = response.choices[0].message.content.strip()
        # 清理可能的 markdown
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️ LLM 分類失敗：{e}")
        return {
            "intent": "ambiguous",
            "risk_level": 2,
            "need_emergency_action": False,
            "need_notification": True,
            "confidence": 0.0,
            "reason": "LLM 分類失敗，保守標記為高關注",
        }


def check_danger(text: str) -> dict:
    """
    完整危險偵測
    回傳：{
        "level": "safe" | "notice" | "concern" | "crisis",
        "keyword": str,
        "intent": str,
        "risk_level": int,
        "need_notification": bool,
        "confidence": float,
        "reason": str,
    }
    """
    flag, keyword = keyword_flag(text)

    # 最高危關鍵字：直接 crisis，不等 LLM
    if flag == "critical":
        return {
            "level": "crisis",
            "keyword": keyword,
            "intent": "self_harm_intent",
            "risk_level": 3,
            "need_notification": True,
            "confidence": 1.0,
            "reason": f"觸發最高危關鍵字：{keyword}",
        }

    # 敏感關鍵字：送 LLM 判斷
    if flag == "sensitive":
        result = llm_classify(text, keyword)
        risk = result.get("risk_level", 0)
        confidence = result.get("confidence", 0.0)

        if risk == 3 or result.get("need_emergency_action", False):
            level = "crisis"
            need_notification = True
        elif risk == 2 and confidence >= 0.65:
            level = "concern"
            need_notification = True
        elif risk >= 1:
            level = "notice"
            need_notification = False
        else:
            level = "safe"
            need_notification = False

        return {
            "level": level,
            "keyword": keyword,
            "intent": result.get("intent", "ambiguous"),
            "risk_level": risk,
            "need_notification": need_notification,
            "confidence": confidence,
            "reason": result.get("reason", ""),
        }

    # 無關鍵字：直接 safe
    return {
        "level": "safe",
        "keyword": "",
        "intent": "knowledge",
        "risk_level": 0,
        "need_notification": False,
        "confidence": 1.0,
        "reason": "無敏感內容",
    }