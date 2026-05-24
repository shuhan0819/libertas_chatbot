"""
執行此腳本建立第一個社工管理員帳號
使用方式：python create_admin.py
"""
import asyncio
from app.database import init_db, AsyncSessionLocal
from app.models import User
from app.auth import hash_password
from sqlalchemy import select


async def create_admin():
    await init_db()

    username = input("請輸入管理員帳號：").strip()
    password = input("請輸入管理員密碼：").strip()
    display_name = input("請輸入顯示名稱（例如：王社工）：").strip()

    async with AsyncSessionLocal() as db:
        # 確認帳號不重複
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"❌ 帳號 '{username}' 已存在")
            return

        admin = User(
            username=username,
            password=hash_password(password),
            display_name=display_name,
            is_admin=1,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        print(f"✅ 管理員帳號建立成功！")
        print(f"   帳號：{admin.username}")
        print(f"   名稱：{admin.display_name}")
        print(f"   ID：{admin.id}")


if __name__ == "__main__":
    asyncio.run(create_admin())
