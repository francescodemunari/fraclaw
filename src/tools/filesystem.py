import os
import shutil
from pathlib import Path
from loguru import logger

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None


# ─── Path allowlist enforcement ───────────────────────────────────────────────

def _check_allowed_path(path: str) -> str | None:
    """
    Resolves the path and verifies it falls within an allowed directory.

    Returns the resolved absolute path string if allowed, or None if blocked.

    Allowed locations:
      1. Any directory listed in config.filesystem_allowed_paths
      2. The project's own data/ directory (workspace, uploads, output, etc.)
         — always allowed regardless of config, so the agent can always write
         generated files without requiring the user to configure their project path.
    """
    from src.config import config

    resolved = Path(path).resolve()

    # Always allow access to the project's data directory
    _project_root = Path(__file__).parent.parent.parent
    _data_dir = (_project_root / "data").resolve()
    if str(resolved).startswith(str(_data_dir)):
        return str(resolved)

    # Check against user-configured allowed paths
    for allowed in config.filesystem_allowed_paths:
        allowed_resolved = Path(allowed).resolve()
        if str(resolved).startswith(str(allowed_resolved)):
            return str(resolved)

    return None  # Blocked


def _blocked_error(path: str) -> dict:
    """Returns a standard security-rejection response."""
    logger.warning(f"🔒 Filesystem access BLOCKED (outside allowed paths): {path}")
    return {
        "error": (
            f"Access denied: '{path}' is outside the allowed directories. "
            "Configure FILESYSTEM_ALLOWED_PATHS in .env to extend access."
        )
    }


# ─── Public functions ─────────────────────────────────────────────────────────

def list_directory(path: str) -> dict:
    """Lists files and folders in a directory."""
    if not _check_allowed_path(path):
        return _blocked_error(path)
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Path '{path}' does not exist."}

        items = []
        for item in p.iterdir():
            items.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0
            })
        return {"path": str(p.resolve()), "items": items}
    except Exception as e:
        return {"error": str(e)}


def read_file(path: str = None) -> dict:
    """Reads the content of a text file."""
    if not path:
        return {"error": "Missing 'path' argument."}
    if not _check_allowed_path(path):
        return _blocked_error(path)
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"File '{path}' not found."}
        return {"path": str(p.resolve()), "content": p.read_text(encoding="utf-8")}
    except Exception as e:
        return {"error": str(e)}


def write_file(path: str = None, content: str = None, overwrite: bool = False) -> dict:
    """Creates or overwrites a text file."""
    if not path or content is None:
        return {"error": "Missing required arguments: 'path' and 'content' are mandatory."}
    if not _check_allowed_path(path):
        return _blocked_error(path)
    try:
        p = Path(path)
        if p.exists() and not overwrite:
            return {"error": f"File '{path}' already exists. Use overwrite=True to replace it."}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "success", "path": str(p.resolve())}
    except Exception as e:
        return {"error": str(e)}


def create_directory(path: str) -> dict:
    """Creates a new directory (and parents if necessary)."""
    if not _check_allowed_path(path):
        return _blocked_error(path)
    try:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Directory created: {path}")
        return {"status": "success", "path": str(p.resolve())}
    except Exception as e:
        logger.error(f"Error creating directory '{path}': {e}")
        return {"error": str(e)}


def delete_item(path: str) -> dict:
    """Moves a file or directory to the system trash (recycling bin)."""
    if not _check_allowed_path(path):
        return _blocked_error(path)
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Path '{path}' does not exist."}

        abs_path = str(p.resolve())

        # Safety check: refuse obviously dangerous paths (belt-and-suspenders)
        if len(abs_path) < 10 or "Windows" in abs_path or "System32" in abs_path:
            return {"error": "Safety Block: This path looks like a system directory and cannot be deleted."}

        if send2trash:
            send2trash(abs_path)
            logger.warning(f"🗑️ Item moved to TRASH: {abs_path}")
            return {"status": "success", "message": f"Item '{path}' has been moved to the Recycle Bin."}
        else:
            # Fallback to standard delete if send2trash is missing
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)
            logger.warning(f"🗑️ Item deleted permanently (send2trash missing): {abs_path}")
            return {"status": "success", "message": f"Item '{path}' deleted permanently (system trash unavailable)."}

    except Exception as e:
        logger.error(f"Error moving path to trash '{path}': {e}")
        return {"error": str(e)}
