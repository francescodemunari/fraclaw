"""
vector.py — Memoria vettoriale con ChromaDB

ChromaDB converte testi in numeri (embeddings) e permette ricerche semantiche:
trovare contenuti "simili nel significato" anche se le parole sono diverse.

Uso attuale: memorizzare frammenti di conversazione/conoscenza per RAG futuro.
Uso futuro: indicizzare interi documenti e interrogarli in linguaggio naturale.

ChromaDB salva tutto su disco in `data/chroma/` — nessun server necessario.
"""

from pathlib import Path

import chromadb
from loguru import logger

from src.config import config

# Lazy initialization — si connette solo al primo utilizzo
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    """Restituisce (o inizializza) la collection ChromaDB."""
    global _client, _collection
    if _collection is None:
        chroma_path = Path(config.chroma_path)
        chroma_path.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(path=str(chroma_path))
        _collection = _client.get_or_create_collection(
            name="demuclaw_memory",
            # distanza coseno: migliore per testi semantici
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"✅ ChromaDB inizializzato: {config.chroma_path} "
            f"({_collection.count()} documenti)"
        )
    return _collection


def store_memory(text: str, metadata: dict | None = None, doc_id: str | None = None) -> str:
    """
    Salva un testo nella memoria vettoriale.

    Args:
        text:     Il testo da memorizzare.
        metadata: Dizionario opzionale con tag (es. {"source": "chat", "topic": "python"}).
        doc_id:   ID univoco; se None, ne viene generato uno automaticamente.

    Returns:
        Il doc_id assegnato.
    """
    import uuid

    collection = _get_collection()
    doc_id = doc_id or str(uuid.uuid4())

    collection.add(
        documents=[text],
        metadatas=[metadata or {}],
        ids=[doc_id],
    )
    logger.debug(f"📌 Memoria vettoriale salvata — id: {doc_id}")
    return doc_id


def search_memory(query: str, n_results: int = 5) -> list[dict]:
    """
    Cerca nella memoria vettoriale i testi più simili alla query.

    Returns:
        Lista di dict con chiavi 'text' e 'metadata'.
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
    """Elimina un documento dalla memoria vettoriale."""
    try:
        collection = _get_collection()
        collection.delete(ids=[doc_id])
        logger.info(f"🗑️ Memoria eliminata: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Errore eliminazione memoria: {e}")
        return False
