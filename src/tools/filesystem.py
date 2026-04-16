"""
filesystem.py — Tool per operazioni su file e cartelle

Tutte le operazioni vengono validate contro la whitelist definita in .env.
Se un percorso non è autorizzato, il tool restituisce un errore di sicurezza
invece di eseguire l'operazione.

Whitelist attuale: C:\\Users\\Admin (e tutte le sottocartelle)
"""

from pathlib import Path

from loguru import logger

from src.config import config


# ─── Whitelist Enforcer ───────────────────────────────────────────────────────

def _is_allowed(path: str) -> bool:
    """
    Verifica che il percorso risolto appartenga a una delle cartelle autorizzate.
    Usa Path.resolve() per neutralizzare path traversal (es. ../../etc/passwd).
    """
    try:
        resolved = Path(path).resolve()
        for allowed_raw in config.filesystem_allowed_paths:
            allowed = Path(allowed_raw).resolve()
            # startswith sul percorso stringa per confronto robusto
            if str(resolved).startswith(str(allowed)):
                return True
        return False
    except Exception:
        return False


def _security_error(path: str) -> dict:
    return {
        "error": (
            f"⛔ Accesso negato: '{path}' non è in una cartella autorizzata.\n"
            f"Cartelle consentite: {', '.join(config.filesystem_allowed_paths)}"
        )
    }


# ─── Tool Functions ───────────────────────────────────────────────────────────

def read_file(path: str) -> dict:
    """
    Legge il contenuto testuale di un file.

    Returns dict con:
        - content: testo del file
        - path: percorso assoluto
        - size_bytes: dimensione in byte
    """
    if not _is_allowed(path):
        return _security_error(path)

    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"File non trovato: {path}"}
        if not p.is_file():
            return {"error": f"Il percorso non è un file: {path}"}

        content = p.read_text(encoding="utf-8", errors="replace")
        logger.info(f"📖 File letto: {p} ({p.stat().st_size} bytes)")
        return {
            "path": str(p),
            "content": content,
            "size_bytes": p.stat().st_size,
        }
    except Exception as e:
        logger.error(f"Errore lettura file '{path}': {e}")
        return {"error": str(e)}


def write_file(path: str, content: str, overwrite: bool = False) -> dict:
    """
    Scrive o crea un file testuale.
    Se il file esiste già e overwrite=False, restituisce un errore sicuro.

    Returns dict con:
        - success: True
        - path: percorso assoluto del file creato
        - bytes_written: byte scritti
    """
    if not _is_allowed(path):
        return _security_error(path)

    try:
        p = Path(path).resolve()
        if p.exists() and not overwrite:
            return {
                "error": (
                    f"Il file '{p.name}' esiste già. "
                    "Usa overwrite=true per sovrascriverlo."
                )
            }
        # Crea le cartelle intermedie se non esistono
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        logger.info(f"✏️ File scritto: {p} ({len(content.encode())} bytes)")
        return {
            "success": True,
            "path": str(p),
            "bytes_written": len(content.encode()),
        }
    except Exception as e:
        logger.error(f"Errore scrittura file '{path}': {e}")
        return {"error": str(e)}


def list_directory(path: str) -> dict:
    """
    Lista file e cartelle in una directory.

    Returns dict con:
        - path: percorso assoluto
        - items: lista di {name, type, path, size_bytes?}
        - count: numero totale di elementi
    """
    if not _is_allowed(path):
        return _security_error(path)

    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"Cartella non trovata: {path}"}
        if not p.is_dir():
            return {"error": f"Il percorso non è una cartella: {path}"}

        items = []
        for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            entry: dict = {
                "name": item.name,
                "type": "file" if item.is_file() else "directory",
                "path": str(item),
            }
            if item.is_file():
                entry["size_bytes"] = item.stat().st_size
            items.append(entry)

        logger.info(f"📂 Cartella listata: {p} ({len(items)} elementi)")
        return {"path": str(p), "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Errore listing cartella '{path}': {e}")
        return {"error": str(e)}
