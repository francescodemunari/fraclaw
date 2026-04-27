"""
monitor_tool.py — Tool for proactive web monitoring
"""

from src.memory.preferences import add_web_monitor, delete_web_monitor

def manage_web_monitor(action: str, title: str, query: str = None, interval_hours: int = 6) -> dict:
    """
    Manages proactive web monitoring (Watchman).
    The bot will periodically check the web and notify you of any news.
    
    Args:
        action: 'add' to add, 'delete' to remove.
        title: Unique name for monitoring (e.g., 'Weather tomorrow', 'RTX 5090 News').
        query: The web search to monitor.
        interval_hours: How often to check in hours (default 6).
    """
    if action == "add":
        if not query:
            return {"status": "error", "message": "Missing query for adding monitor."}
        success = add_web_monitor(title, query, interval=interval_hours)
        if success:
            return {"status": "success", "message": f"Monitoring '{title}' activated. I will notify you of updates every {interval_hours} hours."}
    
    elif action == "delete":
        success = delete_web_monitor(title)
        if success:
            return {"status": "success", "message": f"Monitoring '{title}' removed."}
        else:
            return {"status": "error", "message": "Monitor not found."}
            
    return {"status": "error", "message": "Invalid action."}
