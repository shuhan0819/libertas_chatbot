"""
執行此腳本建立知識庫
使用方式：python build_kb.py
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

CREDENTIALS_PATH = "credentials.json"
KNOWLEDGE_BASE_DIR = "knowledge_base"


def main():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ 找不到 {CREDENTIALS_PATH}")
        sys.exit(1)

    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not folder_id:
        print("❌ 請設定環境變數 GOOGLE_DRIVE_FOLDER_ID")
        sys.exit(1)

    print("=" * 50)
    print("  利伯他茲聊天機器人 - 知識庫建立工具")
    print("=" * 50)

    print("\n📥 從 Google Drive 下載文件...")
    from app.rag.document_loader import load_documents_from_drive
    documents = load_documents_from_drive(CREDENTIALS_PATH, folder_id)

    if not documents:
        print("❌ 沒有找到任何文件")
        sys.exit(1)

    print("\n🏗️ 建立知識庫...")
    from app.rag.knowledge_base import build_knowledge_base
    from app.rag.llm import generate

    build_knowledge_base(
        documents=documents,
        llm_generate_fn=generate,
        save_dir=KNOWLEDGE_BASE_DIR,
    )

    print("\n🎉 知識庫建立完成！")
    print("   現在可以啟動 FastAPI 伺服器了")


if __name__ == "__main__":
    main()
