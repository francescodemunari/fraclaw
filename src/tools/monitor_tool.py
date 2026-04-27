"""
monitor_tool.py — Tool for proactive web monitoring
"""

from src.memory.preferences import add_web_monitor, delete_web_monitor
from src.memory.database import get_connection

def manage_web_monitor(action: str, title: str = None, query: str = None, interval_hours: int = 6) -> dict:
    """
    Manages proactive web monitoring (Watchman).
    The bot will periodically check the web and notify you of any news.

    Args:
        action: 'add' to add, 'remove'/'delete' to remove, 'list' to view all.
        title: Unique name for monitoring (e.g., 'Weather tomorrow', 'RTX 5090 News').
        query: The web search to monitor.
        interval_hours: How often to check in hours (default 6).
    """
    if action == "add":
        if not title or not query:
            return {"status": "error", "message": "Both 'title' and 'query' are required for adding a monitor."}
        success = add_web_monitor(title, query, interval=interval_hours)
        if success:
            return {"status": "success", "message": f"Monitoring '{title}' activated. I will notify you of updates every {interval_hours} hours."}
        return {"status": "error", "message": "Failed to save monitor (may already exist)."}

    elif action in ("delete", "remove"):
        if not title:
            return {"status": "error", "message": "'title' is required to remove a monitor."}
        success = delete_web_monitor(title)
        if success:
            return {"status": "success", "message": f"Monitoring '{title}' removed."}
        return {"status": "error", "message": f"Monitor '{title}' not found."}

    elif action == "list":
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT title, query, interval_hours, is_active, last_check FROM web_monitors ORDER BY title"
            ).fetchall()
            conn.close()
            monitors = [dict(r) for r in rows]
            if not monitors:
                return {"status": "success", "monitors": [], "message": "No active monitors."}
            return {"status": "success", "monitors": monitors, "count": len(monitors)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": f"Unknown action '{action}'. Use 'add', 'remove', or 'list'."}
