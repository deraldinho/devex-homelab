from __future__ import annotations

from dataclasses import dataclass

from .capability_registry import CapabilityRegistry


@dataclass(frozen=True)
class DecisaoCapability:
    autorizada: bool
    capability: str | None
    nivel: str | None
    requer_confirmacao: bool
    razao: str


class PolicyCapabilities:
    def __init__(self, registry: CapabilityRegistry, *, read_auto_allow=(), control_allow=()):
        self._registry = registry
        self._read_auto_allow = frozenset(read_auto_allow)
        self._control_allow = frozenset(control_allow)

    def avaliar(self, nome: str, parametros: dict[str, object], *, confirmacao_humana: bool = False) -> DecisaoCapability:
        try:
            spec = self._registry.obter(nome)
        except KeyError:
            return DecisaoCapability(False, None, None, False, "capability_desconhecida")
        if not spec.validar_parametros(parametros):
            return DecisaoCapability(False, spec.nome, spec.nivel, False, "parametros_invalidos")
        if spec.nivel == "READ":
            permitida = spec.nome in self._read_auto_allow
            return DecisaoCapability(permitida, spec.nome, spec.nivel, False,
                                     "read_allowlisted" if permitida else "read_nao_autorizada")
        if spec.nivel == "CONTROL":
            permitida = spec.nome in self._control_allow
            return DecisaoCapability(permitida, spec.nome, spec.nivel, False,
                                     "control_autorizado" if permitida else "control_nao_autorizado")
        if not confirmacao_humana:
            return DecisaoCapability(False, spec.nome, spec.nivel, True, "confirmacao_humana_obrigatoria")
        return DecisaoCapability(True, spec.nome, spec.nivel, False, "confirmacao_humana_validada")
