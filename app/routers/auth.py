import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.limiter import limiter
from app.models import User, InstitutionSettings
from app.schemas import LoginRequest, TokenResponse, UserResponse, RegisterRequest, ChangePasswordRequest
from app.auth import verify_password, create_access_token, get_current_user, hash_password

router = APIRouter(prefix="/auth", tags=["認證"])


async def _get_gmail_settings(db: AsyncSession):
    """從後台讀取 Gmail 設定"""
    result = await db.execute(select(InstitutionSettings))
    inst = result.scalar_one_or_none()
    if inst:
        return inst.gmail_user or "", inst.gmail_app_password or ""
    return "", ""


@router.post("/register", response_model=UserResponse, summary="使用者自行註冊")
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用者自行註冊，輸入 Gmail、暱稱、帳號、密碼"""
    # 確認帳號不重複
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"帳號 '{body.username}' 已存在",
        )

    # 產生驗證 token（24 小時有效）
    verify_token = str(uuid.uuid4())
    verify_token_expires = datetime.utcnow() + timedelta(hours=24)

    new_user = User(
        username=body.username,
        password=hash_password(body.password),
        display_name=body.display_name,
        email=body.email,
        is_admin=0,
        is_active=True,
        is_verified=False,
        verify_token=verify_token,
        verify_token_expires=verify_token_expires,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # 寄送驗證信
    try:
        gmail_user, gmail_password = await _get_gmail_settings(db)
        from app.email_sender import send_verification_email
        send_verification_email(
            to_email=body.email,
            display_name=body.display_name,
            verify_token=verify_token,
            gmail_user=gmail_user,
            gmail_password=gmail_password,
        )
        print(f"✅ 驗證信已寄至：{body.email}")
    except Exception as e:
        print(f"⚠️ 驗證信寄送失敗：{e}")

    return UserResponse.model_validate(new_user)


@router.get("/verify", summary="信箱驗證")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """使用者點擊驗證連結後呼叫"""
    result = await db.execute(
        select(User).where(User.verify_token == token)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效或已過期的驗證連結",
        )

    if user.verify_token_expires and datetime.utcnow() > user.verify_token_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="驗證連結已過期（有效期 24 小時），請重新申請",
        )

    user.is_verified = True
    user.verify_token = None
    user.verify_token_expires = None
    await db.commit()

    return {"message": "信箱驗證成功！請返回登入頁面登入。"}


@router.post("/login", response_model=TokenResponse, summary="使用者登入")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """輸入帳號密碼，驗證成功後回傳 JWT Token"""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
        )

    # 停用帳號
    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此帳號已被停用，請聯繫社工人員",
        )

    # 未驗證信箱（管理員帳號跳過）
    if user.is_admin == 0 and user.is_verified is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="請先完成信箱驗證，驗證信已寄至你的 Gmail",
        )

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse, summary="取得目前登入的使用者資訊")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return UserResponse.model_validate(current_user)


@router.patch("/change-password", summary="使用者自行修改密碼")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="舊密碼錯誤",
        )
    current_user.password = hash_password(body.new_password)
    await db.commit()
    return {"message": "密碼已成功修改"}


@router.post("/resend-verification", summary="重新寄送驗證信")
async def resend_verification(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="此帳號已完成驗證")

    import uuid
    from datetime import datetime, timedelta
    user.verify_token = str(uuid.uuid4())
    try:
        user.verify_token_expires = datetime.utcnow() + timedelta(hours=24)
    except Exception:
        pass
    await db.commit()

    try:
        gmail_user, gmail_password = await _get_gmail_settings(db)
        from app.email_sender import send_verification_email
        send_verification_email(
            to_email=user.email,
            display_name=user.display_name,
            verify_token=user.verify_token,
            gmail_user=gmail_user,
            gmail_password=gmail_password,
        )
    except Exception as e:
        print(f"⚠️ 驗證信寄送失敗：{e}")

    return {"message": "驗證信已重新寄出，請檢查你的 Gmail"}
