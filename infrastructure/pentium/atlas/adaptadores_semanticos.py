from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .modelo_evento_semantico import (
    EntidadeSemantica,
    EstadoSemantico,
    EventoSemantico,
    TipoEventoSemantico,
)
from .stimulus_model import Stimulus

MAX_FANOUT = 32


class ErroFronteiraSemantica(ValueError):
    pass


class AdaptadorSemantico(Protocol):
    source: str

    def traduzir(self, stimulus: Stimulus) -> tuple[EventoSemantico, ...]: ...


def _estado(status: object) -> EstadoSemantico:
    if not isinstance(status, str):
        raise ErroFronteiraSemantica("status semantico ausente")
    try:
        return EstadoSemantico(status.strip().lower())
    except ValueError as exc:
        raise ErroFronteiraSemantica("status semantico desconhecido") from exc


def _tipo_host(kind: str) -> TipoEventoSemantico:
    mapping = {
        "baseline_observed": TipoEventoSemantico.OBSERVED,
        "status_changed": TipoEventoSemantico.STATE_CHANGED,
        "recovered": TipoEventoSemantico.RECOVERED,
        "source_error": TipoEventoSemantico.SOURCE_ERROR,
    }
    try:
        return mapping[kind]
    except KeyError as exc:
        raise ErroFronteiraSemantica("kind de host desconhecido") from exc


@dataclass(frozen=True)
class AdaptadorStatusHost:
    source: str
    entity: EntidadeSemantica
    scalar_fields: tuple[str, ...] = ()
    metric_fields: tuple[str, ...] = ()
    include_failed_checks: bool = False

    def _attributes(self, payload: Mapping[str, object]) -> dict[str, object]:
        attrs = {key: payload[key] for key in self.scalar_fields if key in payload}
        metrics = payload.get("metrics")
        if self.metric_fields and isinstance(metrics, Mapping):
            for key in self.metric_fields:
                if key in metrics:
                    attrs[key] = metrics[key]
        if self.include_failed_checks:
            checks = payload.get("checks")
            if isinstance(checks, Mapping):
                attrs["failed_checks"] = sum(1 for value in checks.values() if not bool(value))
        return attrs

    def traduzir(self, stimulus: Stimulus) -> tuple[EventoSemantico, ...]:
        if stimulus.source != self.source:
            raise ErroFronteiraSemantica("source nao pertence ao adapter")
        payload = dict(stimulus.payload)
        event = _tipo_host(stimulus.kind)
        state = EstadoSemantico.ERROR if event is TipoEventoSemantico.SOURCE_ERROR else _estado(payload.get("status"))
        try:
            semantic = EventoSemantico(
                entity=self.entity,
                event=event,
                state=state,
                severity=stimulus.severity,
                novelty=stimulus.novelty,
                correlation_id=stimulus.correlation_id,
                attributes=self._attributes(payload),
            )
        except (TypeError, ValueError) as exc:
            raise ErroFronteiraSemantica("payload de host invalido") from exc
        return (semantic,)


class AdaptadorPresencaWifi:
    source = "wifi.presence"
    entity = EntidadeSemantica.WIFI_ZONE

    def _evento(self, stimulus: Stimulus, event: TipoEventoSemantico, state: EstadoSemantico, attrs: Mapping[str, object]) -> EventoSemantico:
        return EventoSemantico(
            entity=self.entity,
            event=event,
            state=state,
            severity=stimulus.severity,
            novelty=stimulus.novelty,
            correlation_id=stimulus.correlation_id,
            attributes=attrs,
        )

    def traduzir(self, stimulus: Stimulus) -> tuple[EventoSemantico, ...]:
        if stimulus.source != self.source:
            raise ErroFronteiraSemantica("source nao pertence ao adapter")
        payload = dict(stimulus.payload)
        if stimulus.kind == "source_error":
            return (self._evento(stimulus, TipoEventoSemantico.SOURCE_ERROR, EstadoSemantico.ERROR, {}),)
        if stimulus.kind == "recovered":
            return (self._evento(stimulus, TipoEventoSemantico.RECOVERED, EstadoSemantico.HEALTHY, {}),)
        if stimulus.kind == "baseline_observed":
            devices = payload.get("devices", ())
            if not isinstance(devices, (list, tuple)):
                raise ErroFronteiraSemantica("devices wifi invalido")
            return (self._evento(stimulus, TipoEventoSemantico.OBSERVED, _estado(payload.get("status")), {"device_count": len(devices)}),)
        if stimulus.kind != "status_changed":
            raise ErroFronteiraSemantica("kind wifi desconhecido")

        raw_events = payload.get("events")
        if not isinstance(raw_events, (list, tuple)):
            raise ErroFronteiraSemantica("events wifi invalido")
        if len(raw_events) > MAX_FANOUT:
            raise ErroFronteiraSemantica("fanout semantico excede bound")
        mapping = {
            "appeared": (TipoEventoSemantico.PRESENCE_APPEARED, EstadoSemantico.PRESENT),
            "missing": (TipoEventoSemantico.PRESENCE_MISSING, EstadoSemantico.MISSING),
            "recovered": (TipoEventoSemantico.PRESENCE_RECOVERED, EstadoSemantico.PRESENT),
            "changed": (TipoEventoSemantico.PRESENCE_CHANGED, EstadoSemantico.PRESENT),
        }
        result: list[EventoSemantico] = []
        for item in raw_events:
            if not isinstance(item, Mapping):
                raise ErroFronteiraSemantica("evento wifi invalido")
            kind = item.get("kind")
            mac = item.get("mac")
            if kind not in mapping or not isinstance(mac, str) or not mac:
                raise ErroFronteiraSemantica("evento wifi desconhecido")
            event, state = mapping[str(kind)]
            attrs: dict[str, object] = {"mac": mac}
            if kind == "changed":
                changed = item.get("changed_fields", ())
                if not isinstance(changed, (list, tuple)):
                    raise ErroFronteiraSemantica("changed_fields wifi invalido")
                attrs["changed_count"] = len(changed)
            try:
                result.append(self._evento(stimulus, event, state, attrs))
            except (TypeError, ValueError) as exc:
                raise ErroFronteiraSemantica("payload wifi invalido") from exc
        if not result:
            devices = payload.get("devices", ())
            if not isinstance(devices, (list, tuple)):
                raise ErroFronteiraSemantica("devices wifi invalido")
            result.append(self._evento(stimulus, TipoEventoSemantico.STATE_CHANGED, _estado(payload.get("status")), {"device_count": len(devices)}))
        return tuple(result)


class FronteiraSemantica:
    def __init__(self, adapters: tuple[AdaptadorSemantico, ...]):
        by_source = {adapter.source: adapter for adapter in adapters}
        if len(by_source) != len(adapters):
            raise ValueError("source semantica duplicada")
        self._adapters = by_source

    def traduzir(self, stimulus: Stimulus) -> tuple[EventoSemantico, ...]:
        adapter = self._adapters.get(stimulus.source)
        if adapter is None:
            raise ErroFronteiraSemantica(f"source sem adapter: {stimulus.source}")
        result = adapter.traduzir(stimulus)
        if len(result) > MAX_FANOUT:
            raise ErroFronteiraSemantica("fanout semantico excede bound")
        return result


def criar_fronteira_semantica_padrao() -> FronteiraSemantica:
    return FronteiraSemantica((
        AdaptadorStatusHost(
            "pentium.self",
            EntidadeSemantica.PENTIUM,
            metric_fields=("memory_available_mb", "disk_free_percent"),
            include_failed_checks=True,
        ),
        AdaptadorStatusHost(
            "core",
            EntidadeSemantica.CORE,
            scalar_fields=("tailscale_online", "ipv4_matches", "ssh_reachable"),
        ),
        AdaptadorStatusHost(
            "x99",
            EntidadeSemantica.X99,
            scalar_fields=("hostname", "uptime_seconds", "last_boot", "error", "error_type"),
        ),
        AdaptadorPresencaWifi(),
    ))
