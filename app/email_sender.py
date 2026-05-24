"""
Gmail SMTP 寄信工具（共用）
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(
    to: list,
    subject: str,
    html: str,
    gmail_user: str = None,
    gmail_password: str = None,
):
    """
    用 Gmail SMTP 寄信
    gmail_user/password 優先用傳入的，沒有才用 .env
    """
    sender = gmail_user or os.getenv("GMAIL_USER", "")
    password = gmail_password or os.getenv("GMAIL_APP_PASSWORD", "")

    if not sender or not password:
        print("⚠️ 未設定 Gmail 寄件帳號")
        return False

    recipients = [r.strip() for r in to if r.strip()]
    if not recipients:
        print("⚠️ 未設定收件人")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        print(f"✅ Email 已寄出至：{', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"❌ Email 寄送失敗：{e}")
        return False


def send_verification_email(
    to_email: str,
    display_name: str,
    verify_token: str,
    base_url: str = None,
    gmail_user: str = None,
    gmail_password: str = None,
):
    if base_url is None:
        base_url = os.getenv("BASE_URL", "http://localhost:3000")
    """寄送信箱驗證信"""
    verify_url = f"{base_url}/verify?token={verify_token}"

    html = f"""
    <div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
        <div style="background:#1a237e;color:white;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;">利伯他茲助理 - 信箱驗證</h2>
        </div>
        <div style="border:1px solid #e0e0e0;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
            <p>嗨，{display_name}！</p>
            <p>感謝你註冊利伯他茲助理系統，請點擊下方按鈕完成信箱驗證：</p>
            <div style="text-align:center;margin:30px 0;">
                <a href="{verify_url}"
                   style="background:#1a237e;color:white;padding:14px 32px;
                          border-radius:6px;text-decoration:none;font-size:16px;font-weight:600;">
                    驗證我的信箱
                </a>
            </div>
            <p style="color:#666;font-size:13px;">
                或複製以下連結到瀏覽器：<br>
                <a href="{verify_url}">{verify_url}</a>
            </p>
            <p style="color:#999;font-size:12px;">
                此連結有效期為 24 小時。如果你沒有申請此帳號，請忽略此信。
            </p>
            <hr style="border:none;border-top:1px solid #e0e0e0;margin:16px 0;">
            <p style="color:#999;font-size:12px;text-align:center;">
                連結已過期？
                <a href="{base_url}/resend-verification" style="color:#1a237e;">重新寄送驗證信</a>
            </p>
        </div>
    </div>"""

    return send_email(
        to=[to_email],
        subject="【利伯他茲助理】請驗證你的信箱",
        html=html,
        gmail_user=gmail_user,
        gmail_password=gmail_password,
    )
