import time
from dataclasses import dataclass

from .capability_registry import CapabilityRegistry


@dataclass(frozen=True)
class DecisaoCapability:
    autorizada: bool
    capability: str | None
    nivel: str | None
    requer_confirmacao: bool
    razao: str
    autonomia: str = "DENY"


class PolicyCapabilities:
    def __init__(self, registry: CapabilityRegistry, *, read_auto_allow=(), control_allow=(),
                 auto_control_allow=(), auto_hosts=(), auto_services=(),
                 cooldown_s: float = 300.0, max_auto_per_window: int = 2,
                 window_s: float = 3600.0, clock=time.monotonic):
        self._registry = registry
        self._read_auto_allow = frozenset(read_auto_allow)
        self._control_allow = frozenset(control_allow)
        self._auto_control_allow = frozenset(auto_control_allow)
        self._auto_hosts = frozenset(auto_hosts)
        self._auto_services = frozenset(auto_services)
        self._cooldown_s = float(cooldown_s)
        self._max_auto_per_window = int(max_auto_per_window)
        self._window_s = float(window_s)
        self._clock = clock
        self._history: list[tuple[float, str, str, str]] = []

    def _control_is_auto_safe(self, nome: str, parametros: dict[str, object]) -> bool:
        return (
            nome in self._auto_control_allow
            and parametros.get("host") in self._auto_hosts
            and parametros.get("service") in self._auto_services
        )

    def registrar_execucao(self, nome: str, parametros: dict[str, object], quando: float | None = None) -> None:
        t = self._clock() if quando is None else float(quando)
        host = str(parametros.get("host") or "")
        service = str(parametros.get("service") or "")
        self._history.append((t, nome, host, service))

    def avaliar(self, nome: str, parametros: dict[str, object], *, confirmacao_humana: bool = False) -> DecisaoCapability:
        try:
            spec = self._registry.obter(nome)
        except KeyError:
            return DecisaoCapability(False, None, None, False, "capability_desconhecida", "DENY")
        if not spec.validar_parametros(parametros):
            return DecisaoCapability(False, spec.nome, spec.nivel, False, "parametros_invalidos", "DENY")
        if spec.nivel == "READ":
            permitida = spec.nome in self._read_auto_allow
            return DecisaoCapability(permitida, spec.nome, spec.nivel, False,
                                     "read_allowlisted" if permitida else "read_nao_autorizada",
                                     "AUTO" if permitida else "DENY")
        if spec.nivel == "CONTROL":
            if self._control_is_auto_safe(spec.nome, parametros):
                now = self._clock()
                host = str(parametros.get("host") or "")
                service = str(parametros.get("service") or "")
                recent = [entry for entry in self._history if entry[1] == spec.nome and entry[2] == host and entry[3] == service]
                if recent:
                    last_time = recent[-1][0]
                    if (now - last_time) < self._cooldown_s:
                        return DecisaoCapability(False, spec.nome, spec.nivel, True, "cooldown_active", "CONFIRM")
                in_window = [entry for entry in recent if (now - entry[0]) <= self._window_s]
                if len(in_window) >= self._max_auto_per_window:
                    return DecisaoCapability(False, spec.nome, spec.nivel, True, "action_budget_exceeded", "CONFIRM")
                return DecisaoCapability(True, spec.nome, spec.nivel, False,
                                         "autonomy_safe_scope", "AUTO")
            if spec.nome in self._control_allow:
                return DecisaoCapability(True, spec.nome, spec.nivel, False,
                                         "control_autorizado", "CONFIRM")
            return DecisaoCapability(False, spec.nome, spec.nivel, True,
                                     "confirmacao_humana_obrigatoria", "CONFIRM")
        if not confirmacao_humana:
            return DecisaoCapability(False, spec.nome, spec.nivel, True,
                                     "confirmacao_humana_obrigatoria", "CONFIRM")
        return DecisaoCapability(True, spec.nome, spec.nivel, False,
                                 "confirmacao_humana_validada", "CONFIRM")
