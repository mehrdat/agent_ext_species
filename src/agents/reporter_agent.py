from __future__ import annotations
from typing import Any, Dict, List, Tuple

# Compose UI model + Markdown report. No LLM required here.

def _status_chip(assessment: Dict[str, Any] | None) -> str:
    if not assessment: return "Unknown"
    s = assessment.get("status") or "Unknown"
    date = assessment.get("assessed_on") or ""
    return f"{s} ({date})" if date else s


def _markdown_report(db: Dict[str, Any], findings: List[Dict[str, Any]], images: List[Dict[str, Any]]) -> str:
    sci = db.get("scientific_name") or "Unknown species"
    common = ", ".join(db.get("common_names") or [])
    tax = db.get("taxonomy") or {}
    assess = db.get("assessment") or {}

    lines = [
        f"# {sci} — {_status_chip(assess)}",
        f"**Common names**: {common or '—'}\n",
        "## Summary",
        (findings[0]["text"] if findings else "No external summary available."),
        "\n## Taxonomy",
        " · ".join([
            f"Kingdom: {tax.get('kingdom', '—')}",
            f"Phylum: {tax.get('phylum', '—')}",
            f"Class: {tax.get('class', '—')}",
            f"Order: {tax.get('order', '—')}",
            f"Family: {tax.get('family', '—')}",
            f"Genus: {tax.get('genus', '—')}",
        ]),
        "\n## Images",
    ]
    for i, im in enumerate(images[:12], 1):
        lines.append(f"{i}. [{im.get('title','Image')}]({im.get('url')}) — {im.get('license','?')} · {im.get('attribution','')}")

    if findings:
        lines.append("\n## Sources")
        for i, f in enumerate(findings, 1):
            lines.append(f"[{i}] {f.get('source','?')}: {f.get('url','')}")

    return "\n".join(lines)


def reporter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    dbres = (state.get("db_results") or {})
    findings = state.get("web_findings") or []
    images = state.get("image_candidates") or []

    ui = {
        "species": dbres.get("scientific_name"),
        "status": _status_chip(dbres.get("assessment")),
        "taxonomy": dbres.get("taxonomy") or {},
        "image_count": len(images),
        "source_count": len(findings),
    }
    md = _markdown_report(dbres, findings, images)
    return {"ui_model": ui, "markdown_report": md}