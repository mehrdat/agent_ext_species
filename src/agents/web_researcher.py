from __future__ import annotations
import asyncio
from typing import Any, Dict, List
import httpx

WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
GBIF_MEDIA = "https://api.gbif.org/v1/occurrence/search"

SAFE_LICENSES = {"CC0", "CC-BY", "CC-BY-SA"}

async def _fetch_json(client: httpx.AsyncClient, url: str, params: Dict[str, Any] | None = None):
    r = await client.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

async def _wiki_summary(client: httpx.AsyncClient, title: str) -> Dict[str, Any] | None:
    try:
        return await _fetch_json(client, WIKI_SUMMARY.format(title=title.replace(" ", "%20")))
    except Exception:
        return None

async def _gbif_images(client: httpx.AsyncClient, scientific_name: str, limit: int = 12) -> List[Dict[str, Any]]:
    params = {
        "scientificName": scientific_name,
        "mediaType": "StillImage",
        "limit": limit,
    }
    try:
        data = await _fetch_json(client, GBIF_MEDIA, params)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for rec in data.get("results", []):
        for m in rec.get("media", []) or []:
            lic = (m.get("license") or "").upper()
            # normalize
            if "CC0" in lic:
                lic_tag = "CC0"
            elif "CC-BY-SA" in lic:
                lic_tag = "CC-BY-SA"
            elif "CC-BY" in lic:
                lic_tag = "CC-BY"
            else:
                lic_tag = lic
            if lic_tag in SAFE_LICENSES:
                out.append({
                    "url": m.get("identifier"),
                    "title": m.get("title") or rec.get("species"),
                    "license": lic_tag,
                    "attribution": rec.get("recordedBy") or rec.get("datasetName") or "GBIF contributor",
                    "source": "GBIF",
                    "width": m.get("width"),
                    "height": m.get("height"),
                })
    return out

async def web_research_async(state: Dict[str, Any]) -> Dict[str, Any]:
    entities = state.get("entities") or []
    sci = entities[0] if entities else None
    user_query = state.get("user_input", "")

    findings: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(headers={"User-Agent": "under-threat-bot/0.1"}) as client:
        wiki = await _wiki_summary(client, sci or user_query)
        if wiki:
            summary = wiki.get("extract")
            url = wiki.get("content_urls", {}).get("desktop", {}).get("page")
            if summary and url:
                findings.append({"text": summary, "url": url, "source": "Wikipedia", "license": "CC-BY-SA"})
            img = wiki.get("originalimage") or wiki.get("thumbnail")
            if img:
                images.append({
                    "url": img.get("source"),
                    "title": wiki.get("title"),
                    "license": "CC-BY-SA",
                    "attribution": "Wikipedia/Wikimedia Commons",
                    "source": "Wikipedia",
                    "width": img.get("width"),
                    "height": img.get("height"),
                })
        if sci:
            gbif_imgs = await _gbif_images(client, sci)
            images.extend(gbif_imgs)

    # De-dup by URL
    seen = set(); unique_imgs = []
    for im in images:
        u = im.get("url")
        if u and u not in seen:
            seen.add(u); unique_imgs.append(im)

    return {
        "web_findings": findings,
        "image_candidates": unique_imgs,
    }

# LangGraph node wrapper

def web_researcher_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return asyncio.run(web_research_async(state))
    except Exception as e:
        errs = list(state.get("errors", []) or [])
        errs.append(f"WebResearcher error: {type(e).__name__}: {e}")
        return {"errors": errs}