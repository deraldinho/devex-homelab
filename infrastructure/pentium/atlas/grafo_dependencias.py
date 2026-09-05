from __future__ import annotations


class GrafoDependencias:
    def __init__(self, capacidade_arestas: int):
        if not isinstance(capacidade_arestas, int) or capacidade_arestas <= 0:
            raise ValueError("capacidade_arestas deve ser inteiro > 0")
        self._capacidade = capacidade_arestas
        self._dependencias: dict[str, set[str]] = {}

    def adicionar_dependencia(self, dependente: str, depende_de: str) -> None:
        dependente = dependente.strip()
        depende_de = depende_de.strip()
        if not dependente or not depende_de:
            raise ValueError("dependente e depende_de sao obrigatorios")
        if dependente == depende_de:
            raise ValueError("self-loop nao permitido")
        atual = self._dependencias.setdefault(dependente, set())
        if depende_de in atual:
            return
        if self._contagem_arestas() >= self._capacidade:
            raise OverflowError("capacidade do grafo excedida")
        atual.add(depende_de)
        if self._alcanca(depende_de, dependente):
            atual.remove(depende_de)
            raise ValueError("ciclo de dependencia nao permitido")

    def dependencias_de(self, entidade_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._dependencias.get(entidade_id, ())))

    def dependentes_transitivos(self, entidade_id: str) -> tuple[str, ...]:
        encontrados: set[str] = set()
        fronteira = [entidade_id]
        while fronteira:
            alvo = fronteira.pop()
            novos = sorted(
                dependente
                for dependente, dependencias in self._dependencias.items()
                if alvo in dependencias and dependente not in encontrados
            )
            encontrados.update(novos)
            fronteira.extend(novos)
        return tuple(sorted(encontrados))

    def dependencias_transitivas(self, entidade_id: str) -> tuple[str, ...]:
        encontrados: set[str] = set()
        fronteira = [entidade_id]
        while fronteira:
            atual = fronteira.pop()
            for dependencia in self._dependencias.get(atual, ()):
                if dependencia not in encontrados:
                    encontrados.add(dependencia)
                    fronteira.append(dependencia)
        return tuple(sorted(encontrados))

    def _alcanca(self, origem: str, destino: str) -> bool:
        visitados: set[str] = set()
        fronteira = [origem]
        while fronteira:
            atual = fronteira.pop()
            if atual == destino:
                return True
            if atual in visitados:
                continue
            visitados.add(atual)
            fronteira.extend(self._dependencias.get(atual, ()))
        return False

    def _contagem_arestas(self) -> int:
        return sum(len(deps) for deps in self._dependencias.values())
