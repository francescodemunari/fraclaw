import os
import shutil
from pathlib import Path
from loguru import logger
try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

def list_directory(path: str) -> dict:
    """Lists files and folders in a directory."""
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
        return {"path": str(p.absolute()), "items": items}
    except Exception as e:
        return {"error": str(e)}

def read_file(path: str = None) -> dict:
    """Reads the content of a text file."""
    if not path:
        return {"error": "Missing 'path' argument."}
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"File '{path}' not found."}
        return {"path": str(p.absolute()), "content": p.read_text(encoding="utf-8")}
    except Exception as e:
        return {"error": str(e)}

def write_file(path: str = None, content: str = None, overwrite: bool = False) -> dict:
    """Creates or overwrites a text file."""
    if not path or content is None:
        return {"error": "Missing required arguments: 'path' and 'content' are mandatory."}
    try:
        p = Path(path)
        if p.exists() and not overwrite:
            return {"error": f"File '{path}' already exists. Use overwrite=True to replace it."}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "success", "path": str(p.absolute())}
    except Exception as e:
        return {"error": str(e)}

def create_directory(path: str) -> dict:
    """Creates a new directory (and parents if necessary)."""
    try:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Directory created: {path}")
        return {"status": "success", "path": str(p.absolute())}
    except Exception as e:
        logger.error(f"Error creating directory '{path}': {e}")
        return {"error": str(e)}

def delete_item(path: str) -> dict:
    """Moves a file or directory to the system trash (recycling bin)."""
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Path '{path}' does not exist."}
        
        # Absolute path for security
        abs_path = str(p.absolute())
        
        # Safety check: avoid deleting root or system folders
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
