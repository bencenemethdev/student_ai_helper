from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import faiss
import numpy as np
from openai import OpenAI
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter


client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    return embedding_model.encode(list(texts)).tolist()

def _get_encoder():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None

def _count_tokens(text: str) -> int:
    enc = _get_encoder()
    if enc is None:
        return max(1, int(len(text.split()) / 0.75))
    return len(enc.encode(text))

def _chunk_text(text: str, *, target_tokens: int = 800, overlap_tokens: int = 120) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunk_size = target_tokens * 4
    chunk_overlap = overlap_tokens * 4

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]

def extract_pdf_text(uploaded_file) -> Tuple[str, int]:
    reader = PdfReader(uploaded_file)
    pages_text: List[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    return "\n\n".join(pages_text).strip(), len(reader.pages)


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    page_span: Tuple[int, int]

def build_chunks_from_pdfs(uploaded_files: Sequence[Any]) -> Tuple[List[Chunk], Dict[str, Any]]:
    chunks: List[Chunk] = []
    stats = {"files": 0, "pages": 0, "chunks": 0, "tokens_est": 0}

    for f in uploaded_files:
        filename = getattr(f, "name", "uploaded.pdf")
        reader = PdfReader(f)
        num_pages = len(reader.pages)
        stats["files"] += 1
        stats["pages"] += num_pages

        all_chunks_with_pages: List[Tuple[str, int, int]] = []
        
        pages_per_block = 5
        for block_start in range(0, num_pages, pages_per_block):
            block_end = min(num_pages, block_start + pages_per_block)
            block_text = ""
            for p_idx in range(block_start, block_end):
                try:
                    block_text += (reader.pages[p_idx].extract_text() or "") + "\n\n"
                except Exception:
                    pass
            
            for ctext in _chunk_text(block_text.strip(), target_tokens=800, overlap_tokens=120):
                all_chunks_with_pages.append((ctext, block_start + 1, block_end))

        for i, (ctext, sp, ep) in enumerate(all_chunks_with_pages):
            cid = f"{filename}::chunk-{i+1}"
            chunks.append(Chunk(id=cid, text=ctext, source=filename, page_span=(sp, ep)))
            stats["tokens_est"] += _count_tokens(ctext)

    stats["chunks"] = len(chunks)
    return chunks, stats

def generate_study_plan(
    *,
    chunks: Sequence[Chunk],
    current_date: date,
    exam_date: date,
    daily_hours: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    total_days = max(1, (exam_date - current_date).days + 1)
    n_chunks = max(0, len(chunks))
    chunks_per_day = max(1, math.ceil(n_chunks / total_days)) if n_chunks else 0

    plan: List[Dict[str, Any]] = []
    chunk_id_to_date: Dict[str, str] = {}

    for day_idx in range(total_days):
        day = current_date + timedelta(days=day_idx)
        day_str = day.isoformat()

        start = day_idx * chunks_per_day
        end = min(n_chunks, (day_idx + 1) * chunks_per_day)
        day_chunks = chunks[start:end] if n_chunks else []

        if not day_chunks:
            plan.append({"date": day_str, "task": "Review / catch-up", "hours": int(daily_hours)})
            continue
        by_source: Dict[str, int] = {}
        for c in day_chunks:
            by_source[c.source] = by_source.get(c.source, 0) + 1
            chunk_id_to_date[c.id] = day_str

        page_ranges = {}
        for c in day_chunks:
            chunk_id_to_date[c.id] = day_str
            if c.source not in page_ranges:
                page_ranges[c.source] = [c.page_span[0], c.page_span[1]]
            else:
                page_ranges[c.source][0] = min(page_ranges[c.source][0], c.page_span[0])
                page_ranges[c.source][1] = max(page_ranges[c.source][1], c.page_span[1])

        pages_summary = ", ".join([
            f"{src}: Pages {pr[0]}–{pr[1]}" for src, pr in sorted(page_ranges.items())
        ])
        task = f"Study: {pages_summary}"
        plan.append({"date": day_str, "task": task, "hours": int(daily_hours)})

    return plan, chunk_id_to_date

def _embed_texts(texts: Sequence[str]) -> np.ndarray:
    vectors = np.array(embed_texts(texts), dtype=np.float32)
    faiss.normalize_L2(vectors)
    return vectors

@dataclass
class VectorIndex:
    index: faiss.Index
    chunks: List[Chunk]
    vectors: np.ndarray

def build_vector_index(chunks: Sequence[Chunk]) -> VectorIndex:
    if not chunks:
        dim = 384  # all-MiniLM-L6-v2
        empty = np.zeros((0, dim), dtype=np.float32)
        index = faiss.IndexFlatIP(dim)
        return VectorIndex(index=index, chunks=[], vectors=empty)

    vectors = _embed_texts([c.text for c in chunks])
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    return VectorIndex(index=index, chunks=list(chunks), vectors=vectors)

def retrieve(
    vdb: VectorIndex,
    query: str,
    *,
    k: int = 5,
    min_score: float = 0.20,
    only_date: Optional[str] = None,
    chunk_id_to_date: Optional[Dict[str, str]] = None,
) -> List[Tuple[Chunk, float]]:
    if not query.strip() or vdb.index.ntotal == 0:
        return []

    qvec = _embed_texts([query])[0:1]
    scores, idxs = vdb.index.search(qvec, k=min(k, max(1, vdb.index.ntotal)))

    results: List[Tuple[Chunk, float]] = []
    for score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
        if idx < 0:
            continue
        ch = vdb.chunks[idx]
        if only_date and chunk_id_to_date:
            if chunk_id_to_date.get(ch.id) != only_date:
                continue
        if score < min_score:
            continue
        results.append((ch, float(score)))

    return results

def rag_chat(
    *,
    vdb: VectorIndex,
    chunk_id_to_date: Dict[str, str],
    question: str,
    current_date: date,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    day_str = current_date.isoformat()
    hits = retrieve(vdb, question, k=6, min_score=0.20, only_date=day_str, chunk_id_to_date=chunk_id_to_date)

    if not hits:
        hits = retrieve(vdb, question, k=6, min_score=0.10)

    if not hits:
        return "I don't know."

    context_blocks = []
    for ch, score in hits:
        context_blocks.append(
            f"[{ch.source} | {ch.id} | score={score:.2f}]\n{ch.text}"
        )
    context = "\n\n---\n\n".join(context_blocks)

    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a Student Helper AI. Answer ONLY from provided context. If not found, say 'I don't know'.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    answer = response.choices[0].message.content
    return (answer or "").strip() or "I don't know."

def generate_flashcards(
    *,
    vdb: VectorIndex,
    chunk_id_to_date: Dict[str, str],
    current_date: date,
    n_cards: int = 5,
    model: str = "llama-3.3-70b-versatile",
) -> List[Dict[str, str]]:
    day_str = current_date.isoformat()
    today_chunks = [
        ch for ch in vdb.chunks if chunk_id_to_date.get(ch.id) == day_str
    ]
    if not today_chunks:
        today_chunks = vdb.chunks[: min(12, len(vdb.chunks))]

    context = "\n\n---\n\n".join([f"[{ch.source}]\n{ch.text}" for ch in today_chunks[:8]])
    if not context.strip():
        return []

    prompt = (
        f"Generate {n_cards} flashcards from the context.\n"
        "Return ONLY valid JSON (no markdown), exactly as a list of objects:\n"
        '[{"question": "...", "answer": "..."}]\n'
        "Keep answers short and factual.\n"
        "Context:\n"
        f"{context}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a Student Helper AI. Answer ONLY from provided context. If not found, say 'I don't know'.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
        cards = []
        for item in data:
            q = str(item.get("question", "")).strip()
            a = str(item.get("answer", "")).strip()
            if q and a:
                cards.append({"question": q, "answer": a})
        return cards[:n_cards]
    except Exception:
        return [{"question": "Could not parse flashcards JSON", "answer": raw[:1000]}]
