from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db
from app.limiter import limiter
from app.routers import auth, admin, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動時初始化資料庫和 RAG"""
    await init_db()

    # 初始化 RAG（在背景執行，不阻塞啟動）
    try:
        from app.rag.pipeline import init_rag
        init_rag()
    except Exception as e:
        print(f"⚠️ RAG 初始化失敗（知識庫可能尚未建立）：{e}")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="社工支持聊天機器人後端 API",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router,  prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(chat.router,  prefix="/api")


@app.get("/", tags=["健康檢查"])
async def root():
    return {"status": "ok", "message": f"{settings.APP_NAME} 後端運行中"}


@app.get("/api/health", tags=["健康檢查"])
async def health_check():
    return {"status": "ok"}
