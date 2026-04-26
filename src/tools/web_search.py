"""
web_search.py — Web search via DuckDuckGo

No API key required. Uses the ddgs library 
to query DuckDuckGo anonymously.
"""

from loguru import logger


def web_search(query: str, max_results: int = 5) -> dict:
    """
    Searches DuckDuckGo and returns the results.
    """
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            # text() returns the result generator
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )

        logger.info(f"🌐 Web search '{query}': {len(results)} results")
        return {"query": query, "results": results, "count": len(results)}

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return {"error": str(e), "query": query}

def news_search(query: str, max_results: int = 5, timelimit: str = None) -> dict:
    """
    Searches DuckDuckGo News and returns recent news articles.
    
    CRITICAL INSTRUCTION: This tool only returns headlines and snippets. If the user expects 
    detailed facts, you MUST use the `read_webpage` tool on one of the returned URLs to 
    read the full text. Do not invent the article content!
    
    Args:
        query: The news topic to search for.
        max_results: Number of articles to return.
        timelimit: Optional time filter. Can be 'd' (past day), 'w' (past week), 'm' (past month), 
                   'y' (past year), or None (any time). Use 'd' if the user explicitly asks for "today".
    """
    try:
        from ddgs import DDGS
        results = []
        
        with DDGS(timeout=10) as ddgs:
            # Use the dedicated news API to prevent hallucinated/generic results
            for r in ddgs.news(query, max_results=max_results, timelimit=timelimit):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "date": r.get("date", "Today"),
                    "snippet": r.get("body", ""),
                    "source": r.get("source", "News")
                })

        logger.info(f"📰 News search '{query}': {len(results)} results")
        return {"query": query, "results": results, "count": len(results)}

    except Exception as e:
        logger.error(f"General news search error: {e}")
        return {"error": str(e), "query": query}

