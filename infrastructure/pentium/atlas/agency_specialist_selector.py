"""Deterministic specialist shortlist selection for Atlas (CP-AA4).

Pure function for selecting specialist agents based on project and candidate pool.
No side effects, no network access, no agent execution.
"""
from __future__ import annotations

import re
from typing import Final

# Project allowlist
_VALID_PROJECTS: Final = frozenset(("atlas", "rei-da-laje", "lanchonete-do-guru"))

# Canonical slugs from pinned catalog (msitarzewski/agency-agents@f99f6aa)
# Legacy slugs accepted ONLY when supplied by trusted provider.
# Canonical and legacy map to the same logical role; at most one per logical role.
_CANONICAL_TO_LEGACY: Final = {
    "sre-site-reliability-engineer": "sre",
    "backend-architect": "backend-engineer",
}

_LEGACY_TO_CANONICAL: Final = {v: k for k, v in _CANONICAL_TO_LEGACY.items()}

# All known logical roles per project (canonical preferred, legacy as fallback)
_PROJECT_ROLES: Final = {
    "atlas": ("sre-site-reliability-engineer", "multi-agent-systems-architect"),
    "rei-da-laje": ("game-designer", "performance-benchmarker"),
    "lanchonete-do-guru": ("backend-architect", "test-automation-engineer"),
}

# Fixed, audited selection signals. Never match against candidate descriptions
# or instructions found in external material. No model output authorizes a role.
# Keys are canonical role slugs.
_ROLE_KEYWORDS: Final = {
    "atlas": {
        "sre-site-reliability-engineer": ("monitoramento", "monitoring", "service", "serviços", "servicos", "sre", "observabilidade"),
        "multi-agent-systems-architect": ("arquitetura", "architecture", "agentes", "agents", "orquestração"),
    },
    "rei-da-laje": {
        "game-designer": ("pipa", "combate", "game", "design", "gameplay"),
        "performance-benchmarker": ("desempenho", "performance", "benchmark", "benchmarking", "fps"),
    },
    "lanchonete-do-guru": {
        "backend-architect": ("backend", "api", "servidor", "database"),
        "test-automation-engineer": ("testes", "tests", "test", "tdd", "automation"),
    },
}

# Validation bounds
_MAX_OBJECTIVE_LEN: Final = 2000
_MAX_CANDIDATES: Final = 25
_MAX_SLUG_LEN: Final = 80
_MAX_DIVISION_LEN: Final = 80
_MAX_DESCRIPTION_LEN: Final = 300

_SLUG_RE: Final = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")


def _validate_project(project: str) -> None:
    if not isinstance(project, str) or project not in _VALID_PROJECTS:
        raise ValueError("project_invalid")


def _validate_objective(objective: str) -> None:
    if not isinstance(objective, str) or not objective.strip() or len(objective) > _MAX_OBJECTIVE_LEN or "\x00" in objective:
        raise ValueError("objective_invalid")


def _validate_candidates(candidates: list[dict]) -> None:
    if not isinstance(candidates, list) or len(candidates) > _MAX_CANDIDATES:
        raise ValueError("candidates_invalid")
    
    seen_slugs = set()
    for c in candidates:
        if not isinstance(c, dict):
            raise ValueError("candidates_invalid")
        
        # Required fields
        slug = c.get("slug")
        division = c.get("division")
        description = c.get("description")
        
        if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug) or len(slug) > _MAX_SLUG_LEN:
            raise ValueError("candidates_invalid")
        if not isinstance(division, str) or not division.strip() or len(division) > _MAX_DIVISION_LEN or "\x00" in division:
            raise ValueError("candidates_invalid")
        if not isinstance(description, str) or len(description) > _MAX_DESCRIPTION_LEN or "\x00" in description:
            raise ValueError("candidates_invalid")
        
        if slug in seen_slugs:
            raise ValueError("candidates_invalid")
        seen_slugs.add(slug)


def select_specialists(
    project: str,
    objective: str,
    candidates: list[dict],
    max_agents: int = 2,
) -> tuple[str, ...]:
    """Select specialist agents for a project from a candidate pool.
    
    Args:
        project: Project identifier (atlas, rei-da-laje, lanchonete-do-guru)
        objective: Task objective (max 2000 chars, bounded)
        candidates: List of candidate dicts with slug, division, description
        max_agents: Maximum agents to select (default 2, max 2)
    
    Returns:
        Tuple of selected specialist slugs (max 2, stable priority order).
        Canonical slugs preferred when both canonical and legacy are present.
    
    Raises:
        ValueError: If any input validation fails
    """
    # Validate inputs
    _validate_project(project)
    _validate_objective(objective)
    _validate_candidates(candidates)
    
    if type(max_agents) is not int or max_agents < 0 or max_agents > 2:
        raise ValueError("max_agents_invalid")
    
    if max_agents == 0:
        return ()
    
    # Get project's prioritized role slugs (canonical)
    project_roles = _PROJECT_ROLES[project]
    
    # Only slugs in the on-demand candidate pool can be selected.
    # Match complete words in the bounded objective; never parse descriptions.
    candidate_slugs = {c["slug"] for c in candidates}
    normalized = objective.casefold()
    
    selected = []
    selected_logical_roles = set()  # Track logical roles to prevent duplicates
    
    for canonical_slug in project_roles:
        # Determine the logical role key (canonical slug is the logical role identifier)
        logical_role = canonical_slug
        
        # Skip if we already selected this logical role
        if logical_role in selected_logical_roles:
            continue
        
        # Get keywords for this canonical role
        keywords = _ROLE_KEYWORDS[project][canonical_slug]
        matched = any(
            re.search(r"(?<!\\w)" + re.escape(word) + r"(?!\\w)", normalized)
            for word in keywords
        )
        
        if not matched:
            continue
        
        # Check if canonical slug is available in candidates
        if canonical_slug in candidate_slugs:
            selected.append(canonical_slug)
            selected_logical_roles.add(logical_role)
        # Fallback to legacy slug ONLY if canonical not present and legacy is in candidates
        elif canonical_slug in _CANONICAL_TO_LEGACY:
            legacy_slug = _CANONICAL_TO_LEGACY[canonical_slug]
            if legacy_slug in candidate_slugs:
                selected.append(legacy_slug)
                selected_logical_roles.add(logical_role)
        
        if len(selected) >= max_agents:
            break
    
    return tuple(selected)