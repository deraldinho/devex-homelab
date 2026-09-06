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
