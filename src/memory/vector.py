"""
vector.py — Vector Memory with ChromaDB

ChromaDB converts text into numbers (embeddings) and allows semantic searches:
finding content "similar in meaning" even if the exact words are different.

Current use: store conversation fragments/knowledge for future RAG.
Future use: index entire documents and query them in natural language.

ChromaDB saves everything to disk in `data/chroma/` — no server needed.
"""

from pathlib import Path

import chromadb
from loguru import logger

from src.config import config

# Lazy initialization — connects only on first use
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    """Returns (or initializes) the ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        chroma_path = Path(config.chroma_path)
        chroma_path.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(path=str(chroma_path))
        _collection = _client.get_or_create_collection(
            name="demuclaw_memory",
            # cosine distance: best for semantic text
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"✅ ChromaDB initialized: {config.chroma_path} "
            f"({_collection.count()} documents)"
        )
    return _collection


def store_memory(text: str, metadata: dict | None = None, doc_id: str | None = None) -> str:
    """
    Saves a text fragment in the vector memory.

    Args:
        text:     The text to store.
        metadata: Optional dict with tags (e.g. {"source": "chat", "topic": "python"}).
        doc_id:   Unique ID; if None, one is automatically generated.

    Returns:
        The assigned doc_id.
    """
    import uuid

    collection = _get_collection()
    doc_id = doc_id or str(uuid.uuid4())

    collection.add(
        documents=[text],
        metadatas=[metadata or {}],
        ids=[doc_id],
    )
    logger.debug(f"📌 Vector memory saved — id: {doc_id}")
    return doc_id


def search_memory(query: str, n_results: int = 5) -> list[dict]:
    """
    Searches vector memory for text fragments most similar to the query.

    Returns:
        List of dicts with keys 'text', 'metadata', and 'distance'.
    """
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, total),
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def delete_memory(doc_id: str) -> bool:
    """Deletes a document from vector memory."""
    try:
        collection = _get_collection()
        collection.delete(ids=[doc_id])
        logger.info(f"🗑️ Memory deleted: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        return False


def clear_all_memories() -> bool:
    """Deletes ALL data from vector memory (ChromaDB Nuclear Reset)."""
    try:
        global _client, _collection
        if _client is None:
            _get_collection()
        
        # Delete and recreate collection
        _client.delete_collection("demuclaw_memory")
        _collection = None
        _get_collection()
        logger.warning("☣️ Vectors reset (ChromaDB Nuclear Reset)")
        return True
    except Exception as e:
        logger.error(f"Error resetting ChromaDB: {e}")
        return False
