"""Read-only natural-language fallback for human conversations.

Plain LLM text is untrusted presentation only. Never parse it into a capability
or use it for planning/execution. Machine/incident paths stay schema-strict.
"""
from __future__ import annotations
import re


_SECRET = re.compile(
    r"(?i)(?:\b(?:bearer\s+|access_token\s*[:=]\s*|(?:password|secret|api_key|token)\s*[:=]\s*)\S+"
    r"|\b(?:sk(?:-proj)?-|ghp_|github_pat_)[A-Za-z0-9_-]{8,})"
)
_ACTION_CLAIMS = re.compile(
    r"(?i)\b(?:reiniciei|executei|instalei|desinstalei|criei|enviei|apaguei|"
    r"deletei|removi|alterei|implantei|deployei|bloqueei)\b"
)
_STRUCTURED_MARKERS = re.compile(
    r"(?i)(?:versao_schema|parametros_intencao|requer_confirmacao|"
    r"<\s*/?\s*(?:system|output_contract|operator_input|retrieved_memories|tool_observation)\b)"
)


def safe_natural_reply(value: object, *, max_chars: int = 2048) -> str | None:
    """Allow compact plain prose only; JSON, commands and secrets fail closed."""
    if not isinstance(value, str) or not 1 <= max_chars <= 2048:
        return None
    text = value.strip()
    if not text or len(text) > max_chars:
        return None
    # Nao transformar erros curtos/rotulos tecnicos como 'nao-json' em fala.
    # Saudações curtas conhecidas permanecem validas.
    greetings = frozenset(("oi", "olá", "ola", "sim", "não", "nao"))
    if not any(ch.isspace() for ch in text) and text.casefold() not in greetings:
        return None
    if text[0] in "[{" or "{" in text or "}" in text or "```" in text:
        return None
    if ("<" in text or ">" in text or _SECRET.search(text)
            or _STRUCTURED_MARKERS.search(text) or _ACTION_CLAIMS.search(text)):
        return None
    if any(ord(ch) < 32 and ch not in "\n\t\r" for ch in text):
        return None
    return text
