from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Callable

from .adaptador_impacto_afetivo import AdaptadorImpactoAfetivo
from .affective_runtime import AffectiveRuntime
from .compositor_visual_afetivo import CompositorVisualAfetivo
from .configuracao_afetiva import carregar_configuracao_afetiva
from .contexto_foco_emocao import ContextoFocoEmocao
from .grafo_dependencias import GrafoDependencias
from .modelo_foco import PoliticaFoco
from .modelo_visual_atlas import EstadoInteracaoVisual
from .motor_afetivo import MotorEstadoAfetivo
from .percepcao import PoliticaConfirmacaoPercepcao
from .pipeline_afetivo_observacional import (
    PipelineAfetivoObservacional,
    carregar_config_observation_affective,
)
from .pipeline_percepcao_correlacao import PipelinePercepcaoCorrelacao
from .adaptador_stimulus_percepcao import ConfigFontePercepcao
from .persistencia_afetiva import RepositorioEstadoAfetivo, restaurar_estado
from .persistencia_contexto_afetivo import RepositorioContextoAfetivo, restaurar_contexto
from .persistencia_foco_emocao import RepositorioFocoEmocao, restaurar_foco_emocao
from .persistencia_percepcao_correlacao import RepositorioPercepcaoCorrelacao
from .stimulus_model import Stimulus
from .visual_state_publisher import VisualStatePublisher

@dataclass
class AffectiveComposition:
    pipeline: PipelineAfetivoObservacional
    runtime_visual: AffectiveRuntime
    pipeline_percepcao: PipelinePercepcaoCorrelacao
    contexto_afetivo: object
    motor_afetivo: MotorEstadoAfetivo
    repo_a1: RepositorioEstadoAfetivo
    repo_a2: RepositorioContextoAfetivo
    repo_a3: RepositorioPercepcaoCorrelacao
    repo_a4: RepositorioFocoEmocao
    allowed_sources: frozenset[str]
    errors_buffer: deque[str]

    def errors(self) -> tuple[str, ...]:
        return tuple(self.errors_buffer)

    def _normalizar(self, stimulus: Stimulus) -> Stimulus | None:
        source = stimulus.source
        if source in self.allowed_sources:
            return stimulus
        if source.startswith("managed."):
            target = source.removeprefix("managed.")
            if target in self.allowed_sources:
                payload = dict(stimulus.payload)
                payload["channel_healthy"] = payload.get("channel_status") == "healthy"
                return replace(stimulus, source=target, payload=payload)
        self.errors_buffer.append(f"ignored_source:{source}")
        return None

    def _persistir(self, resultado) -> None:
        operations = (
            ("a3", lambda: self.repo_a3.salvar(self.pipeline_percepcao.percepcoes(), self.pipeline_percepcao.incidentes_ativos())),
            ("a2", lambda: self.repo_a2.salvar(self.contexto_afetivo)),
            ("a1", lambda: self.repo_a1.salvar(self.motor_afetivo.estado_atual)),
            ("a4", lambda: self.repo_a4.salvar(resultado.resultado_foco_emocao)),
        )
        for name, operation in operations:
            try:
                operation()
            except Exception as exc:
                self.errors_buffer.append(f"persist:{name}:{type(exc).__name__}")

    def processar(self, stimulus: Stimulus):
        routed = self._normalizar(stimulus)
        if routed is None:
            return None
        resultado = self.pipeline.processar(routed)
        if resultado.aceito:
            self._persistir(resultado)
        return resultado

def _load_perception(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("versao_esquema") != 1:
        raise ValueError("config_percepcao versao_esquema deve ser 1")
    configs = {
        source: ConfigFontePercepcao(
            source,
            data["entidade_id"],
            tuple(data["campos_alcance"]),
            data["confianca"],
        )
        for source, data in payload["fontes"].items()
    }
    policy = PoliticaConfirmacaoPercepcao(**payload["politica"])
    caps = payload["capacidades"]
    graph = GrafoDependencias(int(caps["arestas_grafo"]))
    for dependent, dependency in payload.get("dependencias", ()):
        graph.adicionar_dependencia(dependent, dependency)
    return configs, policy, caps, graph


def _load_focus(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("config_foco_emocao schema_version deve ser 1")
    return PoliticaFoco(**payload["foco"]), int(payload["emocao"]["capacidade_nuances"])

def build_affective_composition(
    *,
    config_root: Path,
    state_dir: Path,
    now: Callable[[], str],
    id_factory: Callable[[], str],
) -> AffectiveComposition:
    config_root = Path(config_root)
    state_dir = Path(state_dir)
    instant = now()
    affective_cfg = carregar_configuracao_afetiva(config_root / "config_afetiva.json")
    pipeline_cfg = carregar_config_observation_affective(config_root / "config_observation_affective.json")
    source_cfgs, perception_policy, perception_caps, graph = _load_perception(config_root / "config_percepcao.json")
    focus_policy, nuance_capacity = _load_focus(config_root / "config_foco_emocao.json")

    repo_a1 = RepositorioEstadoAfetivo(state_dir / "affective-state.json")
    repo_a2 = RepositorioContextoAfetivo(
        state_dir / "affective-context.json",
        max(8, pipeline_cfg.capacidade_incidentes * 2),
    )
    repo_a3 = RepositorioPercepcaoCorrelacao(state_dir / "perception-correlation.json")
    repo_a4 = RepositorioFocoEmocao(state_dir / "focus-emotion.json")
    restored_a1 = restaurar_estado(repo_a1, affective_cfg.personalidade, affective_cfg.decaimento, instant)
    restored_a2 = restaurar_contexto(repo_a2)
    restored_a3 = repo_a3.restaurar()
    restored_a4 = restaurar_foco_emocao(repo_a4)

    motor = MotorEstadoAfetivo(affective_cfg.personalidade, affective_cfg.decaimento,
                               restored_a1.estado, now)
    perception = PipelinePercepcaoCorrelacao(
        source_cfgs, perception_policy, graph,
        capacidade_evidencias_por_entidade=int(perception_caps["evidencias_por_entidade"]),
        capacidade_incidentes=int(perception_caps["incidentes"]),
        max_entidades_por_incidente=int(perception_caps["entidades_por_incidente"]),
        id_factory=id_factory,
    )
    perception.restaurar(restored_a3.percepcoes, restored_a3.incidentes)
    visual_runtime = AffectiveRuntime(
        CompositorVisualAfetivo(),
        VisualStatePublisher(state_dir / "visual-state.json"),
        interacao_inicial=EstadoInteracaoVisual(atualizado_em=instant),
    )
    if (
        restored_a4.snapshot is not None
        and restored_a4.snapshot.estado_afetivo.atualizado_em == restored_a1.estado.atualizado_em
    ):
        visual_runtime.atualizar_resultado(restored_a4.snapshot)

    focus_context = ContextoFocoEmocao(focus_policy, nuance_capacity)
    pipeline = PipelineAfetivoObservacional(
        pipeline_percepcao=perception,
        contexto_afetivo=restored_a2.contexto,
        adaptador=AdaptadorImpactoAfetivo(pipeline_cfg.impacto),
        motor_afetivo=motor,
        contexto_foco_emocao=focus_context,
        affective_runtime=visual_runtime,
        capacidade_stimulus_ids=pipeline_cfg.capacidade_stimulus_ids,
        capacidade_incidentes=pipeline_cfg.capacidade_incidentes,
        capacidade_assuntos=pipeline_cfg.capacidade_assuntos,
        capacidade_erros=pipeline_cfg.capacidade_erros,
        janela_reincidencia_s=pipeline_cfg.janela_reincidencia_s,
        limite_repeticoes=pipeline_cfg.limite_repeticoes,
    )
    errors = deque(maxlen=pipeline_cfg.capacidade_erros)
    for origin, result in (
        ("a1", restored_a1), ("a2", restored_a2), ("a3", restored_a3), ("a4", restored_a4),
    ):
        if getattr(result, "erro", None):
            errors.append(f"restore:{origin}:{type(getattr(result, 'erro')).__name__}")
    return AffectiveComposition(
        pipeline, visual_runtime, perception, restored_a2.contexto, motor,
        repo_a1, repo_a2, repo_a3, repo_a4, frozenset(source_cfgs), errors,
    )
