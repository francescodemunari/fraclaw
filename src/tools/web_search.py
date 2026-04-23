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

def news_search(query: str, max_results: int = 5) -> dict:
    """
    News-optimized search version to bypass common rate limits.
    """
    try:
        from ddgs import DDGS
        results = []
        
        # Expand query to force recent results without using API timelimits (unstable)
        expanded_query = f"{query} latest news today"
        
        with DDGS(timeout=10) as ddgs:
            # Attempt 1: standard backend (full results, but higher rate limit risk)
            try:
                for r in ddgs.text(expanded_query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "date": "Today",
                        "snippet": r.get("body", ""),
                        "source": "Web"
                    })
            except Exception as e:
                logger.warning(f"⚠️ Standard text search failed for news ({e}). Falling back to lite...")
            
            # Attempt 2: lite backend (highly resilient) if first attempt fails
            if not results:
                for r in ddgs.text(expanded_query, max_results=max_results, backend="lite"):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "date": "Today (Lite)",
                        "snippet": r.get("body", ""),
                        "source": "Web (Lite)"
                    })

        logger.info(f"📰 News search '{query}': {len(results)} results")
        return {"query": query, "results": results, "count": len(results)}

    except Exception as e:
        logger.error(f"General news search error: {e}")
        return {"error": str(e), "query": query}
