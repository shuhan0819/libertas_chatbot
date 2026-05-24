import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# 預設從 .env 讀取（後台設定優先）
DEFAULT_GMAIL_USER = os.getenv("GMAIL_USER", "")
DEFAULT_GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_RECIPIENTS = os.getenv("ALERT_RECIPIENTS", "").split(",")

LEVEL_CONFIG = {
    "crisis":  {"emoji": "🚨", "label": "立即處理", "color": "#b71c1c", "light": "#ffebee"},
    "concern": {"emoji": "⚠️", "label": "需要關注", "color": "#e65100", "light": "#fff3e0"},
    "notice":  {"emoji": "📋", "label": "留意",     "color": "#1565c0", "light": "#e3f2fd"},
}

INTENT_ZH = {
    "knowledge":          "知識查詢",
    "emotional_distress": "情緒困擾",
    "self_harm_intent":   "自我傷害意圖",
    "violence_intent":    "暴力意圖",
    "ambiguous":          "語意不明",
}


def send_danger_alert(
    user_display_name: str,
    username: str,
    danger_info: dict,
    full_conversation: list,
    recipients: list = None,
    gmail_user: str = None,
    gmail_password: str = None,
):
    """
    寄送危險訊號通報 email
    danger_info: check_danger() 回傳的完整 dict
    """
    level = danger_info.get("level", "concern")
    cfg = LEVEL_CONFIG.get(level, LEVEL_CONFIG["concern"])

    # 收件人
    final_recipients = recipients if recipients else [r.strip() for r in ALERT_RECIPIENTS if r.strip()]
    if not final_recipients:
        print("⚠️ 未設定通報收件人")
        return

    # 寄件帳號
    sender = gmail_user or DEFAULT_GMAIL_USER
    password = gmail_password or DEFAULT_GMAIL_PASSWORD
    if not sender or not password:
        print("⚠️ 未設定 Gmail 寄件帳號或應用程式密碼")
        return

    # 取得判斷資訊
    keyword = danger_info.get("keyword", "")
    intent = INTENT_ZH.get(danger_info.get("intent", "ambiguous"), "不明")
    risk_level = danger_info.get("risk_level", 0)
    confidence = danger_info.get("confidence", 0.0)
    reason = danger_info.get("reason", "")

    # 組合對話記錄 HTML
    conv_html = ""
    for msg in full_conversation:
        role = "使用者" if msg["role"] == "user" else "助理"
        color = "#d32f2f" if msg["role"] == "user" else "#1565c0"
        conv_html += f"""
        <div style="margin:8px 0;padding:8px 12px;border-left:3px solid {color};">
            <strong style="color:{color};">{role}：</strong>
            <span>{msg['content']}</span>
        </div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 風險等級顯示
    risk_bar = ""
    for i in range(4):
        bg = cfg["color"] if i <= risk_level else "#e0e0e0"
        risk_bar += '<span style="display:inline-block;width:20px;height:20px;border-radius:3px;margin-right:3px;background:' + bg + '"></span>'

    html = f"""
    <div style="font-family:sans-serif;max-width:620px;margin:0 auto;">
        <div style="background:{cfg['color']};color:white;padding:16px 20px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;">{cfg['emoji']} 危險訊號通報【{cfg['label']}】</h2>
        </div>
        <div style="border:1px solid #e0e0e0;border-top:none;padding:20px;border-radius:0 0 8px 8px;">

            <div style="background:{cfg['light']};padding:14px;border-radius:6px;margin-bottom:20px;">
                <strong>通報等級：</strong>{cfg['emoji']} {cfg['label']}
                &nbsp;&nbsp;
                <strong>風險分數：</strong>{risk_level}/3
                &nbsp;&nbsp;
                <strong>判斷信心：</strong>{int(confidence * 100)}%
            </div>

            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
                <tr>
                    <td style="padding:6px 0;color:#666;width:120px;">通報時間</td>
                    <td><strong>{now}</strong></td>
                </tr>
                <tr>
                    <td style="padding:6px 0;color:#666;">使用者</td>
                    <td><strong>{user_display_name}（{username}）</strong></td>
                </tr>
                <tr>
                    <td style="padding:6px 0;color:#666;">觸發關鍵字</td>
                    <td>
                        <span style="background:{cfg['light']};color:{cfg['color']};
                            padding:2px 8px;border-radius:4px;font-weight:bold;">
                            {keyword}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="padding:6px 0;color:#666;">意圖類型</td>
                    <td><strong>{intent}</strong></td>
                </tr>
                <tr>
                    <td style="padding:6px 0;color:#666;">系統判斷</td>
                    <td style="color:#555;">{reason}</td>
                </tr>
            </table>

            <hr style="margin:16px 0;border:none;border-top:1px solid #e0e0e0;">
            <h3 style="margin:0 0 12px;color:#333;">對話記錄</h3>
            {conv_html}

            <hr style="margin:16px 0;border:none;border-top:1px solid #e0e0e0;">
            <div style="background:#f5f5f5;padding:12px;border-radius:6px;">
                <p style="margin:0;color:#555;font-size:13px;">
                    ⚠️ 此通報為自動分類結果，請社工進一步評估是否需要介入。
                </p>
            </div>
        </div>
    </div>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{cfg['emoji']}【{cfg['label']}】{user_display_name} — {intent}（風險 {risk_level}/3）"
        msg["From"] = sender
        msg["To"] = ", ".join(final_recipients)
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, final_recipients, msg.as_string())

        print(f"✅ {cfg['emoji']} 危險訊號通報已寄出（{cfg['label']}）至：{', '.join(final_recipients)}")
    except Exception as e:
        print(f"❌ 通報寄送失敗：{e}")