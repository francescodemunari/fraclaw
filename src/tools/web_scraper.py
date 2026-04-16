import httpx
import json
from loguru import logger
from bs4 import BeautifulSoup

# Mettiamo un tetto massimo di caratteri per non intasare il context di Qwen3.5-9B
MAX_CHARS = 40000

async def read_webpage(url: str) -> dict:
    """
    Legge il contenuto testuale completo di una pagina web.
    Step 1: Prova con r.jina.ai (ottimo per JS e Markdown).
    Step 2: Fallback locale se Jina fallisce (451, 403, ecc.).
    """
    if not url.startswith("http"):
        url = "https://" + url

    # 1. TENTATIVO JINA
    try:
        logger.info(f"🕸️ Tentativo lettura con Jina: {url}")
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Demuclaw-AI-Agent/1.0"
        }
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(jina_url, headers=headers)
            if response.status_code == 200:
                data = response.json().get("data", {})
                text = data.get("content", "")
                if text:
                    return _format_result(url, data.get("title", "Senza Titolo"), text)
            
            logger.warning(f"Jina ha risposto con errore {response.status_code}. Provo fallback locale...")
            
    except Exception as e:
        logger.warning(f"Errore Jina: {e}. Provo fallback locale...")

    # 2. FALLBACK LOCALE
    try:
        logger.info(f"🏠 Fallback locale per: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text

            # Estrazione con Readability (stile Nanobot)
            from readability import Document
            doc = Document(html_content)
            title = doc.title()
            summary_html = doc.summary()

            # Pulizia HTML -> Testo
            soup = BeautifulSoup(summary_html, "lxml")
            clean_text = soup.get_text(separator="\n", strip=True)

            if not clean_text:
                 # Se readability fallisce, proviamo bs4 su tutto il body
                 soup_full = BeautifulSoup(html_content, "lxml")
                 clean_text = soup_full.get_text(separator="\n", strip=True)

            return _format_result(url, title, clean_text, source="local-fallback")

    except Exception as e:
        logger.error(f"Fallimento totale lettura {url}: {e}")
        return {"error": f"Impossibile leggere {url} (sia Jina che locale hanno fallito): {str(e)}"}

def _format_result(url, title, text, source="jina"):
    """Formatta e tronca il risultato per l'LLM."""
    truncated = False
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n...[TESTO TRONCATO PER LUNGHEZZA]..."
        truncated = True
        
    return {
        "success": True,
        "url": url,
        "title": title,
        "text_content": text,
        "truncated": truncated,
        "engine": source
    }

