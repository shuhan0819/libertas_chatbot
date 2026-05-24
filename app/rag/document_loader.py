import io
import os
from typing import List
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import PyPDF2
import docx

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service(credentials_path: str):
    """建立 Google Drive 服務"""
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def list_files_in_folder(service, folder_id: str) -> list:
    """列出資料夾內所有支援的檔案"""
    supported_mimes = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/x-markdown",
    ]

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)",
    ).execute()

    files = results.get("files", [])
    return [f for f in files if f["mimeType"] in supported_mimes]


def download_file(service, file_id: str) -> bytes:
    """下載檔案內容"""
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def extract_text_from_pdf(content: bytes) -> str:
    """從 PDF 提取文字"""
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def extract_text_from_docx(content: bytes) -> str:
    """從 Word 文件提取文字"""
    doc = docx.Document(io.BytesIO(content))
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])


def extract_text_from_txt(content: bytes) -> str:
    """從 txt 提取文字"""
    return content.decode("utf-8", errors="ignore")


def load_documents_from_drive(credentials_path: str, folder_id: str) -> List[dict]:
    """
    從 Google Drive 資料夾讀取所有文件
    回傳格式：[{"filename": "xxx.pdf", "content": "文字內容"}]
    """
    service = get_drive_service(credentials_path)
    files = list_files_in_folder(service, folder_id)

    documents = []
    for file in files:
        print(f"📄 讀取：{file['name']}")
        try:
            content = download_file(service, file["id"])

            if file["mimeType"] == "application/pdf":
                text = extract_text_from_pdf(content)
            elif "wordprocessingml" in file["mimeType"]:
                text = extract_text_from_docx(content)
            elif file["mimeType"] in ("text/markdown", "text/x-markdown"):
                text = extract_text_from_txt(content)  # markdown 直接當純文字讀
            else:
                text = extract_text_from_txt(content)

            if text.strip():
                documents.append({
                    "filename": file["name"],
                    "content": text.strip()
                })
                print(f"   ✅ 成功，{len(text)} 字")
            else:
                print(f"   ⚠️ 空文件，跳過")

        except Exception as e:
            print(f"   ❌ 失敗：{e}")

    print(f"\n總共讀取 {len(documents)} 份文件")
    return documents
