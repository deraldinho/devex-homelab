"""Formatting boundary for Atlas native Discord notifications."""
from __future__ import annotations

def format_atlas_alert(message, *, narrated_by=None):
    if not isinstance(message,str):
        raise ValueError("invalid alert message")
    text=message.strip()
    if not text or len(text)>1800:
        raise ValueError("alert message size invalid")
    if narrated_by=="atlas_llm":
        # Already generated and grounded by Atlas's narrative layer.
        return text
    return "**[ALERTA ATLAS]** "+text
