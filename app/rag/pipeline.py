import os
from sentence_transformers import SentenceTransformer
from app.rag.knowledge_base import load_knowledge_base, search, EMBEDDING_MODEL
from app.rag import llm

_embedder = None
_index = None
_metadata = None

KNOWLEDGE_BASE_DIR = "knowledge_base"


def init_rag():
    """初始化 RAG"""
    global _embedder, _index, _metadata

    if _index is not None:
        return

    print("🔄 初始化 RAG 系統...")
    _embedder = SentenceTransformer(EMBEDDING_MODEL)

    if os.path.exists(os.path.join(KNOWLEDGE_BASE_DIR, "index.faiss")):
        _index, _metadata = load_knowledge_base(KNOWLEDGE_BASE_DIR)
    else:
        print("⚠️ 知識庫不存在，請先執行 build_kb.py")
        _index, _metadata = None, None

    print("✅ RAG 系統初始化完成")


def rag_chat(user_message: str, chat_history: list = None) -> dict:
    """完整 RAG 聊天流程"""
    global _embedder, _index, _metadata

    if _index is None or _embedder is None:
        reply = llm.generate_with_context(
            user_message=user_message,
            context="",
            chat_history=chat_history
        )
        return {"reply": reply, "used_rag": False, "sources": []}

    results, has_result = search(
        query=user_message,
        index=_index,
        metadata=_metadata,
        embedder=_embedder,
    )
    print(f"🔍 找到的內容：{[r['content'][:80] for r in results]}")
    
    if has_result:
        context_parts = []
        sources = []
        for r in results:
            context_parts.append(f"【來源：{r['filename']}】\n{r['content']}")
            sources.append(r['filename'])

        context = "\n\n".join(context_parts)
        reply = llm.generate_with_context(
            user_message=user_message,
            context=context,
            chat_history=chat_history
        )
        return {"reply": reply, "used_rag": True, "sources": list(set(sources))}
    else:
        reply = llm.generate_with_context(
            user_message=user_message,
            context="",
            chat_history=chat_history
        )
        return {"reply": reply, "used_rag": False, "sources": []}
