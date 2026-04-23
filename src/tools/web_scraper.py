import httpx
import json
from loguru import logger
from bs4 import BeautifulSoup

# Character limit for LLM context management.
# 20,000 chars is ~5k-6k tokens. This can be increased if LM Studio context is high.
MAX_CHARS = 20000

async def read_webpage(url: str) -> dict:
    """
    Reads the full text content of a webpage.
    Step 1: Attempt via r.jina.ai (best for JS and Markdown).
    Step 2: Local fallback if Jina fails (451, 403, etc.).
    """
    if not url.startswith("http"):
        url = "https://" + url

    # 1. JINA ATTEMPT
    try:
        logger.info(f"🕸️ Attempting read via Jina: {url}")
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Fraclaw-AI-Agent/1.0"
        }
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(jina_url, headers=headers)
            if response.status_code == 200:
                data = response.json().get("data", {})
                text = data.get("content", "")
                if text:
                    return _format_result(url, data.get("title", "No Title"), text)
            
            logger.warning(f"Jina responded with error {response.status_code}. Trying local fallback...")
            
    except Exception as e:
        logger.warning(f"Jina error: {e}. Trying local fallback...")

    # 2. LOCAL FALLBACK
    try:
        logger.info(f"🏠 Local fallback for: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text

            # Extraction via Readability
            from readability import Document
            doc = Document(html_content)
            title = doc.title()
            summary_html = doc.summary()

            # Clean HTML to Text
            soup = BeautifulSoup(summary_html, "lxml")
            clean_text = soup.get_text(separator="\n", strip=True)

            if not clean_text:
                 # If readability fails, try bs4 on full body
                 soup_full = BeautifulSoup(html_content, "lxml")
                 clean_text = soup_full.get_text(separator="\n", strip=True)

            return _format_result(url, title, clean_text, source="local-fallback")

    except Exception as e:
        logger.error(f"Total failure reading {url}: {e}")
        return {"error": f"Impossible to read {url} (Both Jina and local fallback failed): {str(e)}"}

def _format_result(url, title, text, source="jina"):
    """Formats and truncates the result for the LLM."""
    truncated = False
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n...[TEXT TRUNCATED DUE TO LENGTH]..."
        truncated = True
        
    return {
        "success": True,
        "url": url,
        "title": title,
        "text_content": text,
        "truncated": truncated,
        "engine": source
    }
