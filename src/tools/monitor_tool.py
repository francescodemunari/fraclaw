"""
monitor_tool.py — Tool per il monitoraggio web proattivo
"""

from src.memory.preferences import add_web_monitor, delete_web_monitor

def manage_web_monitor(action: str, title: str, query: str = None, interval_hours: int = 6) -> dict:
    """
    Gestisce i monitoraggi web proattivi (Watchman).
    Il bot controllerà periodicamente il web e ti avviserà se ci sono novità.
    
    Args:
        action: 'add' per aggiungere, 'delete' per rimuovere.
        title: Nome univoco del monitoraggio (es. 'Meteo domani', 'News RTX 5090').
        query: La ricerca web da monitorare.
        interval_hours: Ogni quante ore controllare (default 6).
    """
    if action == "add":
        if not query:
            return {"status": "error", "message": "Query mancante per l'aggiunta del monitoraggio."}
        success = add_web_monitor(title, query, interval=interval_hours)
        if success:
            return {"status": "success", "message": f"Monitoraggio '{title}' attivato. Ti avviserò se trovo novità ogni {interval_hours} ore."}
    
    elif action == "delete":
        success = delete_web_monitor(title)
        if success:
            return {"status": "success", "message": f"Monitoraggio '{title}' rimosso."}
        else:
            return {"status": "error", "message": "Monitoraggio non trovato."}
            
    return {"status": "error", "message": "Azione non valida."}
