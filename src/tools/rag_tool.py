"""
rag_tool.py — Knowledge Base Module (RAG)
"""

from pathlib import Path
from loguru import logger
from src.memory.vector import store_memory, search_memory

def learn_from_document(path: str) -> dict:
    """
    Reads a document (PDF, TXT, MD), splits it into chunks and saves it in long-term memory.
    
    Args:
        path: Absolute path of the file to index.
    """
    p = Path(path)
    if not p.exists():
        return {"status": "error", "message": "File not found."}
        
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
            return {"status": "error", "message": f"Format '{suffix}' not supported for indexing."}
            
        if not text.strip():
            return {"status": "error", "message": "The document seems empty or unreadable."}
            
        # Chunking — approx 1000 characters with overlap
        chunks = _chunk_text(text, chunk_size=1000, overlap=200)
        
        for i, chunk in enumerate(chunks):
            store_memory(
                text=chunk,
                metadata={"source": p.name, "path": str(p), "chunk": i},
                doc_id=f"{p.name}_{i}"
            )
            
        return {
            "status": "success", 
            "message": f"Document '{p.name}' successfully indexed into {len(chunks)} fragments."
        }
    except Exception as e:
        logger.error(f"Indexing error for {path}: {e}")
        return {"status": "error", "message": f"Internal error: {str(e)}"}

def search_knowledge(query: str) -> dict:
    """
    Searches the library of saved documents for information relevant to the query.
    """
    results = search_memory(query, n_results=5)
    if not results:
        return {"status": "success", "results": [], "message": "No information found in Knowledge Base."}
        
    formatted = []
    for r in results:
        formatted.append({
            "content": r["text"],
            "source": r["metadata"].get("source", "Unknown")
        })
        
    return {"status": "success", "results": formatted}

def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Simple chunker to split text into overlapping blocks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks
