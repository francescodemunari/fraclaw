"""
web_search.py — Ricerca web con DuckDuckGo

Nessuna API key richiesta. Usa la libreria duckduckgo-search
che interroga DuckDuckGo in modo anonimo.
"""

from loguru import logger


def web_search(query: str, max_results: int = 5) -> dict:
    """
    Cerca su DuckDuckGo e restituisce i risultati.
    """
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )

        logger.info(f"🌐 Web search '{query}': {len(results)} risultati")
        return {"query": query, "results": results, "count": len(results)}

    except Exception as e:
        logger.error(f"Errore web search: {e}")
        return {"error": str(e), "query": query}

def news_search(query: str, max_results: int = 5) -> dict:
    """
    Versione ottimizzata per notizie. Usa ddgs.text aggiungendo parole chiave
    temporali per evitare i blocchi 403 della tab News.
    """
    try:
        from ddgs import DDGS
        import re

        # Rimuove l'anno per evitare filtri DDG
        clean_query = re.sub(r'\b(2026|2025)\b', '', query, flags=re.IGNORECASE).strip()

        results = []
        with DDGS() as ddgs:
            # Ricerchiamo con parole chiave "oggi" e "notizie" per simulare la tab News senza subire blocchi
            search_query = f"{clean_query} notizie oggi news"
            for r in ddgs.text(search_query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                        "status": "Snippet parziale. Per riassumere o verificare, USA IL TOOL read_webpage sull'URL."
                    }
                )

        logger.info(f"📰 News search '{clean_query}': {len(results)} risultati")
        return {"query": clean_query, "results": results, "count": len(results)}

    except Exception as e:
        logger.error(f"Errore news search: {e}")
        return {"error": str(e), "query": query}
