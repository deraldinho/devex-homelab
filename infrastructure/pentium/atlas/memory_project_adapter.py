"""Atlas Memory Project Adapter — Observador de eventos de projeto.

Captura eventos de repositórios (commits, PRs, issues) e alimenta
o MemoryGraph com entidades de projeto, decisões e padrões.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .memory_graph import Entity, EntityType, MemoryGraph, Relation, RelationType


_DECISION_PATTERNS = (
    re.compile(r"(?:decisão|decision|escolha|escolhemos|adotamos|politica|policy):\s*(.+)", re.IGNORECASE),
    re.compile(r"(?:padrão|pattern|convenção):\s*(.+)", re.IGNORECASE),
)

_PATTERN_KEYWORDS = {
    "container-first", "tdd", "git-as-source-of-truth", "ssh-managed",
    "allowlist", "default-deny", "deterministic", "bounded",
    "local-first", "immutable-tag", "rollback-safe",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProjectEvent:
    """Evento observável de um projeto."""
    project_id: str
    event_type: str          # "commit", "pr_merged", "issue_opened", "issue_closed"
    title: str
    description: str = ""
    author: str = ""
    sha: str = ""
    timestamp: str = ""
    repository: str = ""

    def __post_init__(self) -> None:
        if not self.project_id or not self.project_id.strip():
            raise ValueError("project_id nao pode ser vazio")
        if not self.event_type or not self.event_type.strip():
            raise ValueError("event_type nao pode ser vazio")
        if not self.title or not self.title.strip():
            raise ValueError("title nao pode ser vazio")


class MemoryProjectAdapter:
    """Observa eventos de projeto e alimenta o MemoryGraph.

    Responsabilidades:
    - Garantir que o projeto e repositório existam como entidades
    - Detectar decisões e padrões em commits/PRs
    - Criar relações entre projetos, repositórios e decisões
    """

    def __init__(self, graph: MemoryGraph):
        self._graph = graph

    def process_event(self, event: ProjectEvent) -> list[str]:
        """Processa um evento de projeto e retorna lista de entity_ids criados/atualizados."""
        now = event.timestamp or _utc_now()
        affected: list[str] = []

        # 1. Garantir entidade do projeto
        proj_id = f"proj:{event.project_id}"
        existing = self._graph.get_entity(proj_id)
        if existing is None:
            self._graph.add_entity(Entity(
                entity_id=proj_id,
                entity_type=EntityType.PROJECT,
                name=event.project_id,
                description=f"Projeto {event.project_id}",
                created_at=now,
                updated_at=now,
                importance=0.7,
            ))
            affected.append(proj_id)

        # 2. Garantir entidade do repositório se disponível
        if event.repository:
            repo_id = f"repo:{event.repository}"
            if self._graph.get_entity(repo_id) is None:
                self._graph.add_entity(Entity(
                    entity_id=repo_id,
                    entity_type=EntityType.REPOSITORY,
                    name=event.repository,
                    description=f"Repositório {event.repository}",
                    created_at=now,
                    updated_at=now,
                ))
                self._graph.add_relation(Relation(
                    source_id=proj_id,
                    target_id=repo_id,
                    relation_type=RelationType.OWNS,
                    created_at=now,
                ))
                affected.append(repo_id)

        # 3. Detectar decisões arquiteturais
        decisions = self._extract_decisions(event)
        for decision_text in decisions:
            dec_id = self._decision_id(event.project_id, decision_text)
            self._graph.add_entity(Entity(
                entity_id=dec_id,
                entity_type=EntityType.DECISION,
                name=decision_text[:80],
                description=f"Decisão identificada em {event.event_type}: {event.title}",
                properties={"source_event": event.event_type, "sha": event.sha},
                created_at=now,
                updated_at=now,
                importance=0.8,
            ))
            self._graph.add_relation(Relation(
                source_id=proj_id,
                target_id=dec_id,
                relation_type=RelationType.DECIDED_BY,
                created_at=now,
            ))
            affected.append(dec_id)

        # 4. Detectar padrões mencionados
        patterns = self._extract_patterns(event)
        for pattern_name in patterns:
            pat_id = f"pattern:{pattern_name}"
            if self._graph.get_entity(pat_id) is None:
                self._graph.add_entity(Entity(
                    entity_id=pat_id,
                    entity_type=EntityType.PATTERN,
                    name=pattern_name,
                    description=f"Padrão arquitetural: {pattern_name}",
                    created_at=now,
                    updated_at=now,
                    importance=0.6,
                ))
            self._graph.add_relation(Relation(
                source_id=proj_id,
                target_id=pat_id,
                relation_type=RelationType.PATTERN_OF,
                created_at=now,
            ))
            if pat_id not in affected:
                affected.append(pat_id)

        return affected

    def ensure_homelab_baseline(self) -> list[str]:
        """Cria entidades baseline do homelab se não existirem."""
        now = _utc_now()
        affected: list[str] = []
        baseline = [
            ("proj:devex-homelab", EntityType.PROJECT, "DevEx HomeLab",
             "Plataforma de infraestrutura do homelab", 0.9),
            ("proj:l2jtoren", EntityType.PROJECT, "L2jToren",
             "Gameserver Lineage II Interlude", 0.9),
            ("node:x99", EntityType.NODE, "x99",
             "Workstation de desenvolvimento", 0.7),
            ("node:core", EntityType.NODE, "Core",
             "homelab.compute — Ubuntu 26.04, Docker runtime", 0.9),
            ("node:pentium", EntityType.NODE, "Pentium",
             "homelab.control — Control plane, Atlas, heartbeat", 0.9),
            ("person:operador", EntityType.PERSON, "Operador",
             "Mantenedor do homelab", 1.0),
        ]
        for eid, etype, name, desc, imp in baseline:
            if self._graph.get_entity(eid) is None:
                self._graph.add_entity(Entity(
                    entity_id=eid, entity_type=etype, name=name,
                    description=desc, created_at=now, updated_at=now,
                    importance=imp, pinned=True,
                ))
                affected.append(eid)

        # Relações baseline
        baseline_rels = [
            ("proj:l2jtoren", "node:core", RelationType.RUNS_ON),
            ("proj:l2jtoren", "node:x99", RelationType.RUNS_ON),
            ("proj:devex-homelab", "node:core", RelationType.OWNS),
            ("proj:devex-homelab", "node:pentium", RelationType.OWNS),
            ("proj:devex-homelab", "node:x99", RelationType.OWNS),
            ("node:pentium", "node:core", RelationType.MONITORS),
            ("person:operador", "proj:devex-homelab", RelationType.OWNS),
            ("person:operador", "proj:l2jtoren", RelationType.OWNS),
        ]
        for src, tgt, rtype in baseline_rels:
            self._graph.add_relation(Relation(
                source_id=src, target_id=tgt, relation_type=rtype,
                created_at=now,
            ))

        return affected

    def _extract_decisions(self, event: ProjectEvent) -> list[str]:
        """Extrai decisões de um evento baseado em padrões textuais."""
        decisions: list[str] = []
        text = f"{event.title} {event.description}"
        for pattern in _DECISION_PATTERNS:
            for match in pattern.finditer(text):
                decision = match.group(1).strip()
                if len(decision) >= 5:
                    decisions.append(decision[:200])
        return decisions

    def _extract_patterns(self, event: ProjectEvent) -> list[str]:
        """Extrai padrões arquiteturais mencionados no evento."""
        text = f"{event.title} {event.description}".lower()
        found: list[str] = []
        for kw in _PATTERN_KEYWORDS:
            if kw in text and kw not in found:
                found.append(kw)
        return found

    @staticmethod
    def _decision_id(project_id: str, decision_text: str) -> str:
        """Gera ID determinístico para uma decisão."""
        import hashlib
        h = hashlib.sha256(f"{project_id}:{decision_text}".encode()).hexdigest()[:12]
        return f"dec:{project_id}:{h}"
