"""
rag_tool.py — Modulo per la Knowledge Base (RAG)
"""

from pathlib import Path
from loguru import logger
from src.memory.vector import store_memory, search_memory

def learn_from_document(path: str) -> dict:
    """
    Legge un documento (PDF, TXT, MD), lo divide in pezzi e lo salva nella memoria a lungo termine.
    
    Args:
        path: Percorso assoluto del file da indicizzare.
    """
    p = Path(path)
    if not p.exists():
        return {"status": "error", "message": "File non trovato."}
        
    text = ""
    suffix = p.suffix.lower()
    
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(p)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif suffix in [".txt", ".md", ".py", ".js"]:
            text = p.read_text(encoding="utf-8", errors="replace")
        else:
            return {"status": "error", "message": f"Formato '{suffix}' non supportato per l'indicizzazione."}
            
        if not text.strip():
            return {"status": "error", "message": "Il documento sembra vuoto o non leggibile."}
            
        # Divisione in pezzi (Chunking) — circa 1000 caratteri con overlap
        chunks = _chunk_text(text, chunk_size=1000, overlap=200)
        
        for i, chunk in enumerate(chunks):
            store_memory(
                text=chunk,
                metadata={"source": p.name, "path": str(p), "chunk": i},
                doc_id=f"{p.name}_{i}"
            )
            
        return {
            "status": "success", 
            "message": f"Documento '{p.name}' indicizzato con successo in {len(chunks)} frammenti."
        }
    except Exception as e:
        logger.error(f"Errore indicizzazione {path}: {e}")
        return {"status": "error", "message": f"Errore interno: {str(e)}"}

def search_knowledge(query: str) -> dict:
    """
    Cerca nella biblioteca di documenti salvati informazioni rilevanti per la query.
    """
    results = search_memory(query, n_results=5)
    if not results:
        return {"status": "success", "results": [], "message": "Nessuna informazione trovata nella Knowledge Base."}
        
    formatted = []
    for r in results:
        formatted.append({
            "content": r["text"],
            "source": r["metadata"].get("source", "Ignota")
        })
        
    return {"status": "success", "results": formatted}

def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Semplice chunker per dividere il testo in blocchi sovrapposti."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks
