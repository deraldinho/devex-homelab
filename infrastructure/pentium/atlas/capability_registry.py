from __future__ import annotations

from dataclasses import dataclass


_NIVEIS = {"READ", "CONTROL", "DESTRUCTIVE"}


@dataclass(frozen=True)
class CapabilitySpec:
    nome: str
    nivel: str
    parametros: tuple[str, ...]
    tipos_parametros: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.nome, str) or not self.nome.strip():
            raise ValueError("nome nao pode ser vazio")
        if self.nivel not in _NIVEIS:
            raise ValueError("nivel invalido")
        if any(not isinstance(p, str) or not p.strip() for p in self.parametros):
            raise ValueError("parametros invalidos")
        tipos = dict(self.tipos_parametros)
        if set(tipos) - set(self.parametros):
            raise ValueError("tipo declarado para parametro desconhecido")
        if any(tipo not in {"str", "int", "bool"} for tipo in tipos.values()):
            raise ValueError("tipo de parametro invalido")

    def validar_parametros(self, valores: dict[str, object]) -> bool:
        if set(valores) != set(self.parametros):
            return False
        tipos = dict(self.tipos_parametros)
        python_types = {"str": str, "int": int, "bool": bool}
        for nome, valor in valores.items():
            tipo = tipos.get(nome, "str")
            if not isinstance(valor, python_types[tipo]):
                return False
            if tipo == "str" and not valor.strip():
                return False
        return True


class CapabilityRegistry:
    def __init__(self, specs):
        mapa = {}
        for spec in specs:
            if not isinstance(spec, CapabilitySpec):
                raise TypeError("spec deve ser CapabilitySpec")
            if spec.nome in mapa:
                raise ValueError("capability duplicada")
            mapa[spec.nome] = spec
        self._specs = mapa

    def listar(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def obter(self, nome: str) -> CapabilitySpec:
        try:
            return self._specs[nome]
        except KeyError as exc:
            raise KeyError(f"capability desconhecida: {nome}") from exc


def atlas_capability_registry() -> CapabilityRegistry:
    """Canonical Atlas capability registry, including M2 CONTROL intents."""
    specs = [
        CapabilitySpec("get_host_status", "READ", ("host",), tipos_parametros=(("host", "str"),)),
        CapabilitySpec("get_cluster_vitals", "READ", ("host",), tipos_parametros=(("host", "str"),)),
        CapabilitySpec("l2j_get_status", "READ", ()),
        CapabilitySpec("l2j_get_dashboards", "READ", ()),
        CapabilitySpec("l2j_check_jvm", "READ", ()),
        CapabilitySpec("l2j_docker_stats", "READ", ()),
        CapabilitySpec("l2j_get_logs", "READ", ("container", "lines"), tipos_parametros=(("container", "str"), ("lines", "int"))),
        CapabilitySpec("l2j_run_tests", "READ", ("test_target",), tipos_parametros=(("test_target", "str"),)),
        CapabilitySpec("l2j_inspect_persistence", "READ", ("filter_term", "lines"), tipos_parametros=(("filter_term", "str"), ("lines", "int"))),
        CapabilitySpec("git_get_status", "READ", ("project",), tipos_parametros=(("project", "str"),)),
        CapabilitySpec("git_recent_commits", "READ", ("project", "count"), tipos_parametros=(("project", "str"), ("count", "int"))),
        CapabilitySpec("task_status", "READ", ()),
        CapabilitySpec("task_create", "CONTROL", ("objective", "area"), tipos_parametros=(("objective", "str"), ("area", "str"))),
        CapabilitySpec("task_complete", "CONTROL", ("reason",), tipos_parametros=(("reason", "str"),)),
        CapabilitySpec("task_abandon", "CONTROL", ("reason",), tipos_parametros=(("reason", "str"),)),
        CapabilitySpec("start_service", "CONTROL", ("host", "service"), tipos_parametros=(("host", "str"), ("service", "str"))),
        CapabilitySpec("stop_service", "CONTROL", ("host", "service"), tipos_parametros=(("host", "str"), ("service", "str"))),
        CapabilitySpec("restart_service", "CONTROL", ("host", "service"), tipos_parametros=(("host", "str"), ("service", "str"))),
        CapabilitySpec("restart_container", "CONTROL", ("host", "container"), tipos_parametros=(("host", "str"), ("container", "str"))),
        CapabilitySpec("reboot_host", "DESTRUCTIVE", ("host",), tipos_parametros=(("host", "str"),)),
        CapabilitySpec("workspace_status", "READ", ()),
        CapabilitySpec("workspace_list", "READ", ("area",)),
        CapabilitySpec("workspace_read", "READ", ("area", "path")),
        CapabilitySpec("workspace_search", "READ", ("query",)),
        CapabilitySpec("workspace_create_note", "CONTROL", ("path", "content")),
        CapabilitySpec("workspace_write", "CONTROL", ("area", "path", "content")),
        CapabilitySpec("workspace_append", "CONTROL", ("area", "path", "content")),
        CapabilitySpec("workspace_mkdir", "CONTROL", ("area", "path")),
        CapabilitySpec("workspace_move", "CONTROL", ("area", "path", "destination_area", "destination_path")),
        CapabilitySpec("workspace_archive", "CONTROL", ("area", "path")),
        CapabilitySpec("workspace_trash", "CONTROL", ("area", "path")),
        CapabilitySpec("workspace_restore", "CONTROL", ("trash_id",)),
        CapabilitySpec("workspace_purge", "DESTRUCTIVE", ("trash_id",)),
        CapabilitySpec("discord_create_channel", "CONTROL", ("name", "topic"), tipos_parametros=(("name", "str"), ("topic", "str"))),
        CapabilitySpec("discord_rename_channel", "CONTROL", ("channel", "new_name"), tipos_parametros=(("channel", "str"), ("new_name", "str"))),
        CapabilitySpec("discord_send_alert", "CONTROL", ("channel", "message"), tipos_parametros=(("channel", "str"), ("message", "str"))),
        CapabilitySpec("discord_create_note", "CONTROL", ("content",), tipos_parametros=(("content", "str"),)),
        CapabilitySpec("discord_create_incident", "CONTROL", ("slug", "description"), tipos_parametros=(("slug", "str"), ("description", "str"))),
        CapabilitySpec("discord_resolve_incident", "CONTROL", ("slug", "post_mortem"), tipos_parametros=(("slug", "str"), ("post_mortem", "str"))),
        CapabilitySpec("discord_purge_messages", "DESTRUCTIVE", ("quantity",), tipos_parametros=(("quantity", "int"),)),
    ]
    return CapabilityRegistry(specs)
