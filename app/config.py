from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7天
    APP_NAME: str = "利伯他茲聊天機器人"
    DEBUG: bool = False
    GROQ_API_KEY: str
    RESEND_API_KEY: str = ""
    ALERT_RECIPIENTS: str = ""
    ALERT_FROM: str = "onboarding@resend.dev"
    GOOGLE_DRIVE_FOLDER_ID: str = ""
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GOOGLE_DRIVE_AUDIO_FOLDER_ID: str = ""
    BASE_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    class Config:
        env_file = ".env"

settings = Settings()
