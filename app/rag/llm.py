import os
from openai import OpenAI
from dotenv import load_dotenv
import random
import opencc
_converter = opencc.OpenCC("s2twp")

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LOCAL_LLM_API_KEY", "local"),
    base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8080/v1")
)
MODEL = "qwen2.5-7b-instruct-q4_k_m"


# ──────────────────────────────────────────
# 多樣化同理確認句
# ──────────────────────────────────────────
EMPATHY_OPENERS = [
    "聽起來你最近承受了很多⋯",
    "謝謝你願意跟我說這些。",
    "你能說出來，其實很不容易。",
    "我注意到你現在好像很不好受。",
    "你說的這些讓我很在意。",
    "願意說出來，代表你還在努力。",
    "我聽到你了。",
    "這些感受都是真實的，不需要假裝沒事。",
    "你不用一個人扛著這些。",
    "能感受到你現在很辛苦。",
]

# ──────────────────────────────────────────
# 系統提示詞
# ──────────────────────────────────────────

SYSTEM_PROMPT = """你是利伯他茲教育基金會的社工支持助理，專門陪伴藥癮康復、更生、或生活遭遇困境的服務對象。

【核心原則】
1. 不得提供任何醫療診斷、藥物建議或治療方案，遇到醫療問題請引導就醫
2. 回覆請使用溫暖、口語化的繁體中文，避免學術或官方語氣
3. 每次回覆控制在150字以內，簡潔有力
4. 不做說教，不評判，不責備
5. 優先讓對方感受到被理解，再提供建議或資訊

【情境回應方式】

▍毒癮／酒癮相關
- 去污名化：「這不代表你失敗了」「掙扎是正常的」
- 降低羞愧感，不用「你應該⋯」的句型
- 減害導向：先幫對方撐過當下衝動，再引導求助
- 復發情境：「你願意說出來很重要」「之前的努力沒有白費」

▍情緒低落／絕望感
- 先同理，後引導
- 不急著給建議，先讓對方感覺被聽見
- 適時提供資源：安心專線1925、生命線1995、張老師1980

▍家庭關係
- 協助整理想法，提供說話的方式建議
- 「關係修復需要時間，可以從小的互動開始」

▍生活需求（租屋、法律文件等）
- 用白話說明，避免專業術語
- 主動提供相關資源或申請條件

▍毒品知識詢問（低危情境）
若使用者詢問毒品相關知識（名稱、成分、法規等），在回答後自然加入一句關懷：
- 「這些物質對身體和心理都有嚴重影響，如果你或身邊的人有相關困擾，可以撥打安心專線 1925。」
不要每次都用同一句，自然融入即可，不要太突兀。

【轉介資源】
遇到危機情境時可提供：
- 安心專線：1925（24小時）
- 生命線：1995
- 張老師：1980
- 家暴性侵：113
- 福利諮詢：1957
- 男性關懷：0800-013-999
- 老年支持：0800-228-585

【禁止事項】
- 不診斷任何身心疾病
- 不建議具體藥物或劑量
- 不評判過去的行為
- 不說「你應該早點⋯」「怎麼會這樣⋯」之類的話
- 【強制要求】你的所有回覆必須使用台灣繁體中文，絕對禁止使用簡體中文，違反此規定的回覆無效"""


def generate(prompt: str, max_tokens: int = 512) -> str:
    """基本文字生成，用於 Pseudo Query 生成"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,
        timeout=30,
    )
    return _converter.convert(response.choices[0].message.content.strip())


def generate_with_context(
    user_message: str,
    context: str = "",
    chat_history: list = None,
) -> str:
    """帶有 RAG context 和對話歷史的生成"""

    opener = random.choice(EMPATHY_OPENERS)
    system = SYSTEM_PROMPT + f"\n\n【本次回覆建議以這類語氣開場，但不要照抄，自然融入即可】\n範例開場：「{opener}」"

    if context:
        system += f"\n\n【重要：請優先根據以下資料回答，資料中有明確說明的就直接引用，不要用自己的猜測替代】\n\n{context}"

    messages = [{"role": "system", "content": system}]

    if chat_history:
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=512,
        temperature=0.75,
        timeout=30,
    )
    return _converter.convert(response.choices[0].message.content.strip())