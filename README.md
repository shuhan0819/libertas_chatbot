# 利伯他茲社工支持聊天機器人（Libertas Chatbot）

為財團法人利伯他茲教育基金會開發的 AI 社工支持系統，服務藥癮康復、更生等高風險族群，提供 24 小時陪伴支持、資訊查詢與危機偵測功能。

---

## 功能列表

### 使用者端
- **帳號系統**：註冊（含 Gmail 信箱驗證）、登入、修改密碼、重寄驗證信
- **RAG 知識庫**：FAISS 向量搜尋 + Pseudo Query Reranker，支援 PDF / DOCX / Markdown
- **語音功能**：Whisper STT 語音輸入、Edge TTS 語音播放
- **四級危險偵測**：關鍵字模糊比對 + 本地 LLM 語意判斷，自動 Gmail 通報
- **聊天介面**：大字體老年友善設計、側邊欄可收起、標題編輯、刪除對話

### 社工後台
- **帳號管理**：新增 / 停用 / 啟用 / 重設密碼 / 永久刪除使用者
- **對話記錄查閱**：含語音播放
- **危險訊號管理**：查閱（依等級篩選）與處理危險事件
- **機構設定**：電話、地址、開放時間、通報 Email、Gmail 寄件設定
- **知識庫後台重建**：進度條顯示 + Email 完成通知

---

## 技術架構

| 層級 | 技術 |
|------|------|
| 前端 | React 19 + Material UI v9 + Axios |
| 後端 | FastAPI (Python 3.11) + Uvicorn |
| 資料庫 | Supabase (PostgreSQL) + SQLAlchemy Async |
| 認證 | JWT (python-jose) + Bcrypt |
| 速率限制 | SlowAPI |
| LLM | 本地 Qwen 2.5 7B（OpenAI 相容 API，透過 llama.cpp） |
| 嵌入模型 | BAAI/bge-small-zh-v1.5（本地） |
| 語音 STT | OpenAI Whisper（本地） |
| 語音 TTS | Edge TTS（zh-TW-HsiaoChenNeural） |
| 知識庫 | FAISS + Pseudo Query Reranker |
| 危險通報 | Gmail SMTP |
| 文件讀取 | Google Drive API |

---

## 危險偵測系統

四級風險架構：

| 等級 | 觸發條件 | AI 回應方式 | Email 通報 | 後台紀錄 |
|------|---------|------------|-----------|---------|
| **crisis** | 22 個最高危關鍵字（遺書、跳樓等）直接觸發 | 融入底線資源與專線 | ✓ 立即 | ✓ |
| **concern** | 敏感詞 + LLM 判斷高風險（risk_level≥2） | 同理回覆 + 自然帶入支持資源 | ✓ 立即 | ✓ |
| **notice** | 敏感詞 + LLM 判斷中等風險 | 正常 RAG 回覆 | ✗ | ✓ |
| **safe** | 無敏感內容 | 正常 RAG 回覆 | ✗ | ✗ |

- 最高危關鍵字：直接標記 crisis，不等 LLM，避免延遲
- 模糊比對臨界值：82%（最高危）/ 80%（敏感詞），處理常見打字錯誤

---

## 環境需求

- Python 3.11
- Node.js 18+
- Anaconda（建議）
- ffmpeg（Whisper 依賴）
- llama.cpp 或其他 OpenAI 相容本地 LLM 服務（預設監聽 `localhost:8080`）

---

## 安裝步驟

### 1. 建立虛擬環境

```bash
conda create -n libertas_chatbot python=3.11 -y
conda activate libertas_chatbot
```

### 2. 安裝 ffmpeg

手動下載後放入 PATH：
- 下載：https://github.com/BtbN/FFmpeg-Builds/releases
- 選 `ffmpeg-master-latest-win64-gpl-shared.zip`

### 3. 安裝 Python 套件

```bash
pip install -r requirements.txt
```

### 4. 安裝前端套件

```bash
cd libertas-frontend
npm install
```

---

## 環境變數設定

在 `libertas_chatbot/` 根目錄建立 `.env`（參考 `.env.example`）：

```env
# 資料庫
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database

# JWT
JWT_SECRET_KEY=你的隨機密鑰（建議 64 位十六進制）
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# 應用程式
APP_NAME=利伯他茲聊天機器人
DEBUG=False
BASE_URL=http://localhost:3000
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# 本地 LLM（llama.cpp 或相容服務）
LOCAL_LLM_API_KEY=local
LOCAL_LLM_BASE_URL=http://localhost:8080/v1

# Google Drive（知識庫文件 & 音檔）
GOOGLE_DRIVE_FOLDER_ID=知識庫文件資料夾ID
GOOGLE_DRIVE_AUDIO_FOLDER_ID=音檔存放資料夾ID

# Gmail（驗證信 & 危險通報）
GMAIL_USER=寄件Gmail帳號
GMAIL_APP_PASSWORD=16位數應用程式密碼
ALERT_RECIPIENTS=通報收件Email（多個用逗號分隔）

# GROQ（備用，RAG 重建時可選用較小模型）
GROQ_API_KEY=gsk_...
```

> **`.env` 與 `credentials.json` 絕對不可上傳至 GitHub。**

---

## Google Drive 服務帳號設定

1. 至 [Google Cloud Console](https://console.cloud.google.com/) 建立服務帳號
2. 下載 JSON 金鑰，命名為 `credentials.json` 放於 `libertas_chatbot/` 根目錄
3. 將服務帳號 Email 加入 Google Drive 資料夾的「共用」名單（至少 Viewer 權限）

---

## Supabase 資料表初始化

首次部署時於 Supabase Dashboard → SQL Editor 執行：

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(200);
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token_expires TIMESTAMP WITH TIME ZONE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE institution_settings ADD COLUMN IF NOT EXISTS gmail_user VARCHAR(200);
ALTER TABLE institution_settings ADD COLUMN IF NOT EXISTS gmail_app_password VARCHAR(200);
```

---

## 啟動方式

### 1. 建立知識庫（首次執行）

```bash
conda activate libertas_chatbot
python build_kb.py
```

### 2. 啟動本地 LLM

使用 llama.cpp 或相容服務，確認 OpenAI 相容 API 監聽於 `localhost:8080`。

### 3. 啟動後端

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 啟動前端（另開終端機）

```bash
cd libertas-frontend
npm start
```

瀏覽器開啟 http://localhost:3000

---

## 初始管理員帳號

```bash
python create_admin.py
```

---

## 部署說明（伺服器）

```bash
# clone 專案
git clone https://github.com/shuhan0819/libertas_chatbot.git
cd libertas_chatbot

# 安裝環境（同安裝步驟）
# 設定 .env 與 credentials.json

# 正式環境後端（多 workers）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 前端 build
cd libertas-frontend
npm run build
```

正式環境建議將 `ALLOWED_ORIGINS` 設為實際的前端 domain（如 `https://your-domain.com`）。

---

## API 速率限制

| 端點 | 限制 |
|------|------|
| `POST /api/auth/login` | 10 次 / 分鐘 |
| `POST /api/chat/voice` | 20 次 / 分鐘 |
| `POST /api/admin/rebuild-kb` | 5 次 / 分鐘 |

語音上傳檔案大小上限：10 MB。

---

## 注意事項

- **本地 LLM**：需先啟動 llama.cpp 或相容服務（預設 `localhost:8080`），知識庫重建建議使用較小模型節省資源
- **Supabase 免費方案**：資料庫限制 500MB，建議定期清理舊對話
- **Gmail 應用程式密碼**：需先開啟兩步驟驗證才能建立（[設定說明](https://support.google.com/accounts/answer/185833)）
- **`credentials.json`** 已由 `.gitignore` 排除，不可手動加入版控
- **`.ipynb_checkpoints/`** 已由 `.gitignore` 排除，Jupyter checkpoint 可能含敏感資訊副本

---

## 畫面截圖

### 登入介面
![登入介面](screenshots/login.png)

### 聊天介面
![聊天介面](screenshots/chat.png)

### 社工後台 — 使用者管理
![使用者管理](screenshots/admin_users.png)

### 社工後台 — 對話記錄
![對話記錄](screenshots/admin_chat.png)

### 社工後台 — 危險訊號
![危險訊號](screenshots/admin_danger.png)

---
> ⚠️ 所有畫面截圖均為測試資料，非真實服務對象資訊