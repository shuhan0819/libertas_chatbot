import os
import json
import pickle
import numpy as np
import faiss
from typing import List, Tuple
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 10
RERANK_TOP_K = 3
SCORE_THRESHOLD = 0.1


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """將長文本切成小塊"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def build_knowledge_base(
    documents: List[dict],
    llm_generate_fn,
    save_dir: str = "knowledge_base",
    progress_callback=None,
):
    """
    建立知識庫
    progress_callback(current, total): 可選，用於回報進度
    """
    os.makedirs(save_dir, exist_ok=True)

    print("🔄 載入嵌入模型...")
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    all_chunks = []
    all_metadata = []

    for doc in documents:
        chunks = split_text(doc["content"])
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({
                "filename": doc["filename"],
                "chunk_index": i,
                "content": chunk
            })

    total_chunks = len(all_chunks)
    print(f"📦 共 {total_chunks} 塊文字，開始生成 Pseudo Query...")

    pseudo_queries = []
    for i, chunk in enumerate(all_chunks):
        print(f"   生成 Pseudo Query {i+1}/{total_chunks}...")

        # 回報進度
        if progress_callback:
            progress_callback(i + 1, total_chunks)

        prompt = f"""以下是一段文件內容，請生成一個最可能對應這段內容的繁體中文問題。
只輸出問題本身，不要有其他說明：

{chunk}"""
        try:
            pq = llm_generate_fn(prompt, max_tokens=50)
            pseudo_queries.append(pq.strip())
        except Exception as e:
            print(f"   ⚠️ 生成失敗，使用原文替代：{e}")
            pseudo_queries.append(chunk[:100])

    print("🔢 向量化 Pseudo Query...")
    embeddings = embedder.encode(pseudo_queries, show_progress_bar=True)
    embeddings = np.array(embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    faiss.write_index(index, os.path.join(save_dir, "index.faiss"))
    with open(os.path.join(save_dir, "metadata.pkl"), "wb") as f:
        pickle.dump(all_metadata, f)
    with open(os.path.join(save_dir, "pseudo_queries.json"), "w", encoding="utf-8") as f:
        json.dump(pseudo_queries, f, ensure_ascii=False, indent=2)

    print(f"✅ 知識庫建立完成，儲存於 {save_dir}/")
    return index, all_metadata


def load_knowledge_base(save_dir: str = "knowledge_base"):
    """載入已建立的知識庫"""
    index = faiss.read_index(os.path.join(save_dir, "index.faiss"))
    with open(os.path.join(save_dir, "metadata.pkl"), "rb") as f:
        metadata = pickle.load(f)
    print(f"✅ 知識庫載入完成，共 {index.ntotal} 筆")
    return index, metadata


def search(
    query: str,
    index,
    metadata: List[dict],
    embedder: SentenceTransformer,
    top_k: int = RERANK_TOP_K,
    threshold: float = SCORE_THRESHOLD
) -> Tuple[List[dict], bool]:
    """搜尋知識庫"""
    query_embedding = embedder.encode([query], convert_to_numpy=True)
    query_embedding = np.array(query_embedding, dtype=np.float32)
    faiss.normalize_L2(query_embedding)

    scores, indices = index.search(query_embedding, min(TOP_K, index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0 and score >= threshold:
            results.append({**metadata[idx], "score": float(score)})

    results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
    return results, len(results) > 0
