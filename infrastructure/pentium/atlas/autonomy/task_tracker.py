"""Atlas Task Tracker — Gestão proativa de tarefas.

Permite ao Atlas criar, priorizar e acompanhar tarefas derivadas
de observações, tendências, hipóteses e comandos do operador.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    CRITICAL = "critical"     # P0
    HIGH = "high"             # P1
    MEDIUM = "medium"         # P2
    LOW = "low"               # P3
    INFORMATIONAL = "info"    # P4

_PRIORITY_ORDER = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
    TaskPriority.INFORMATIONAL: 4,
}


class TaskSource(str, Enum):
    INCIDENT = "incident"
    TREND = "trend"
    HYPOTHESIS = "hypothesis"
    OPERATOR = "operator"
    SELF_OBSERVATION = "self_observation"


@dataclass
class AtlasTask:
    """Tarefa rastreada pelo Atlas."""
    task_id: str
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    source: TaskSource = TaskSource.SELF_OBSERVATION
    status: TaskStatus = TaskStatus.OPEN
    related_entities: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    source_ref: str = ""      # ID do incidente/tendência/hipótese de origem

    def __post_init__(self) -> None:
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id nao pode ser vazio")
        if not self.title or not self.title.strip():
            raise ValueError("title nao pode ser vazio")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}


class TaskTracker:
    """Tracker de tarefas proativo persistido em JSON.

    Priorização determinística:
    INCIDENT > TREND > HYPOTHESIS > OPERATOR > SELF_OBSERVATION
    Dentro de cada source, prioridade por TaskPriority.
    """

    MAX_OPEN = 50
    MAX_HISTORY = 200

    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, AtlasTask] = {}
        self._load()

    def create(
        self,
        task_id: str,
        title: str,
        *,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        source: TaskSource = TaskSource.SELF_OBSERVATION,
        related_entities: list[str] | None = None,
        source_ref: str = "",
    ) -> AtlasTask:
        """Cria uma nova tarefa. Rejeita se limite ativo excedido."""
        open_count = sum(1 for t in self._tasks.values() if not t.is_terminal)
        if open_count >= self.MAX_OPEN:
            raise OverflowError(f"Limite de {self.MAX_OPEN} tarefas abertas atingido")

        # Deduplicação por source_ref
        if source_ref:
            for t in self._tasks.values():
                if t.source_ref == source_ref and not t.is_terminal:
                    return t  # Retorna existente

        now = _utc_now()
        task = AtlasTask(
            task_id=task_id,
            title=title,
            description=description,
            priority=priority,
            source=source,
            related_entities=related_entities or [],
            created_at=now,
            updated_at=now,
            source_ref=source_ref,
        )
        self._tasks[task_id] = task
        self._save()
        return task

    def update_status(self, task_id: str, status: TaskStatus, note: str = "") -> AtlasTask | None:
        task = self._tasks.get(task_id)
        if task is None or task.is_terminal:
            return None
        task.status = status
        task.updated_at = _utc_now()
        if status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            task.completed_at = task.updated_at
        if note:
            task.description = f"{task.description}\n[{task.updated_at}] {note}".strip()
        self._save()
        return task

    def get(self, task_id: str) -> AtlasTask | None:
        return self._tasks.get(task_id)

    def list_open(self) -> list[AtlasTask]:
        """Retorna tarefas abertas ordenadas por prioridade."""
        open_tasks = [t for t in self._tasks.values() if not t.is_terminal]
        return sorted(
            open_tasks,
            key=lambda t: (
                _PRIORITY_ORDER.get(t.priority, 99),
                t.created_at,
            ),
        )

    def list_by_source(self, source: TaskSource) -> list[AtlasTask]:
        return [t for t in self._tasks.values() if t.source == source]

    def list_all(self, *, limit: int = 50) -> list[AtlasTask]:
        sorted_t = sorted(self._tasks.values(), key=lambda t: t.updated_at, reverse=True)
        return sorted_t[:limit]

    def suggest_from_trend(self, metric_key: str, direction: str, projection: str) -> AtlasTask:
        """Cria tarefa sugerida a partir de tendência detectada."""
        task_id = f"trend:{metric_key}:{direction}"
        return self.create(
            task_id=task_id,
            title=f"Tendência {direction} detectada em {metric_key}",
            description=f"Projeção: {projection}. Investigar e prevenir.",
            priority=TaskPriority.HIGH if direction == "rising" else TaskPriority.MEDIUM,
            source=TaskSource.TREND,
            source_ref=task_id,
        )

    def suggest_from_hypothesis(self, hypothesis_id: str, title: str) -> AtlasTask:
        """Cria tarefa sugerida a partir de hipótese confirmada."""
        task_id = f"hypothesis:{hypothesis_id}"
        return self.create(
            task_id=task_id,
            title=f"Ação recomendada: {title}",
            priority=TaskPriority.MEDIUM,
            source=TaskSource.HYPOTHESIS,
            source_ref=hypothesis_id,
        )

    def task_count(self, *, open_only: bool = False) -> int:
        if open_only:
            return sum(1 for t in self._tasks.values() if not t.is_terminal)
        return len(self._tasks)

    def _save(self) -> None:
        # Enforce history limit
        if len(self._tasks) > self.MAX_HISTORY:
            terminal = sorted(
                [t for t in self._tasks.values() if t.is_terminal],
                key=lambda t: t.completed_at or t.updated_at,
            )
            while len(self._tasks) > self.MAX_HISTORY and terminal:
                oldest = terminal.pop(0)
                del self._tasks[oldest.task_id]

        data = {}
        for tid, t in self._tasks.items():
            data[tid] = {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
                "priority": t.priority.value,
                "source": t.source.value,
                "status": t.status.value,
                "related_entities": t.related_entities,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "completed_at": t.completed_at,
                "source_ref": t.source_ref,
            }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for tid, item in data.items():
                self._tasks[tid] = AtlasTask(
                    task_id=item["task_id"],
                    title=item["title"],
                    description=item.get("description", ""),
                    priority=TaskPriority(item.get("priority", "medium")),
                    source=TaskSource(item.get("source", "self_observation")),
                    status=TaskStatus(item.get("status", "open")),
                    related_entities=list(item.get("related_entities", [])),
                    created_at=str(item.get("created_at", "")),
                    updated_at=str(item.get("updated_at", "")),
                    completed_at=str(item.get("completed_at", "")),
                    source_ref=str(item.get("source_ref", "")),
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
