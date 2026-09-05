from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .contexto_afetivo import ContextoAfetivo
from .modelo_contexto_afetivo import (
    EntidadeAfetiva,
    EstadoExpectativa,
    Expectativa,
    ExperienciaOperacional,
    TipoEntidadeAfetiva,
    TipoExpectativa,
    TipoExperienciaOperacional,
    VinculoAfetivo,
)


class ContextoAfetivoSalvoInvalido(ValueError):
    pass


class OrigemRestauracaoContexto(str, Enum):
    ESTADO_SALVO = "estado_salvo"
    VAZIO_POR_AUSENCIA = "vazio_por_ausencia"
    VAZIO_POR_ESTADO_INVALIDO = "vazio_por_estado_invalido"


@dataclass(frozen=True)
class ResultadoRestauracaoContexto:
    contexto: ContextoAfetivo
    origem: OrigemRestauracaoContexto
    erro: str | None = None


class RepositorioContextoAfetivo:
    def __init__(self, caminho: Path, capacidade_historico: int):
        if not isinstance(capacidade_historico, int) or capacidade_historico <= 0:
            raise ValueError("capacidade_historico deve ser inteiro > 0")
        self._caminho = Path(caminho)
        self._capacidade = capacidade_historico

    @property
    def capacidade_historico(self) -> int:
        return self._capacidade

    def salvar(self, contexto: ContextoAfetivo) -> None:
        if contexto.capacidade_historico != self._capacidade:
            raise ValueError("capacidade do contexto difere da capacidade do repositorio")
        payload = _serializar_contexto(contexto)
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        try:
            with temporario.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporario, self._caminho)
            if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                fd = os.open(self._caminho.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporario.unlink(missing_ok=True)

    def carregar(self) -> ContextoAfetivo | None:
        if not self._caminho.exists():
            return None
        try:
            payload = json.loads(self._caminho.read_text(encoding="utf-8"))
            if payload.get("versao_esquema") != 1:
                raise ValueError("contexto afetivo versao_esquema deve ser 1")
            return _desserializar_contexto(payload, self._capacidade)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ContextoAfetivoSalvoInvalido(str(exc)) from exc


def restaurar_contexto(repositorio: RepositorioContextoAfetivo) -> ResultadoRestauracaoContexto:
    try:
        contexto = repositorio.carregar()
        if contexto is None:
            return ResultadoRestauracaoContexto(
                ContextoAfetivo(repositorio.capacidade_historico),
                OrigemRestauracaoContexto.VAZIO_POR_AUSENCIA,
            )
        return ResultadoRestauracaoContexto(
            contexto,
            OrigemRestauracaoContexto.ESTADO_SALVO,
        )
    except ContextoAfetivoSalvoInvalido as exc:
        return ResultadoRestauracaoContexto(
            ContextoAfetivo(repositorio.capacidade_historico),
            OrigemRestauracaoContexto.VAZIO_POR_ESTADO_INVALIDO,
            str(exc),
        )


def _serializar_contexto(contexto: ContextoAfetivo) -> dict:
    entidades = [
        {
            "entidade_id": item.entidade_id,
            "nome": item.nome,
            "tipo": item.tipo.value,
            "incorporada": item.incorporada,
        }
        for item in contexto.entidades()
    ]
    vinculos = [
        {
            "entidade_id": item.entidade_id,
            "importancia": item.importancia,
            "proximidade": item.proximidade,
            "responsabilidade": item.responsabilidade,
            "dependencia_operacional": item.dependencia_operacional,
            "familiaridade": item.familiaridade,
            "confianca_operacional": item.confianca_operacional,
        }
        for item in contexto.vinculos()
    ]
    expectativas = [
        {
            "expectativa_id": item.expectativa_id,
            "entidade_id": item.entidade_id,
            "tipo": item.tipo.value,
            "criada_em": item.criada_em,
            "inicio_previsto_em": item.inicio_previsto_em,
            "limite_em": item.limite_em,
            "encerrada_com": item.encerrada_com.value if item.encerrada_com else None,
        }
        for item in contexto.expectativas()
    ]
    historico = {
        entidade.entidade_id: [
            {
                "experiencia_id": item.experiencia_id,
                "entidade_id": item.entidade_id,
                "tipo": item.tipo.value,
                "ocorrido_em": item.ocorrido_em,
            }
            for item in contexto.historico_de(entidade.entidade_id)
        ]
        for entidade in contexto.entidades()
        if contexto.historico_de(entidade.entidade_id)
    }
    return {
        "versao_esquema": 1,
        "entidades": entidades,
        "vinculos": vinculos,
        "expectativas": expectativas,
        "historico": historico,
    }


def _desserializar_contexto(payload: dict, capacidade: int) -> ContextoAfetivo:
    contexto = ContextoAfetivo(capacidade)
    for dados in payload["entidades"]:
        contexto.cadastrar_entidade(EntidadeAfetiva(
            dados["entidade_id"],
            dados["nome"],
            TipoEntidadeAfetiva(dados["tipo"]),
            dados["incorporada"],
        ))
    for dados in payload["vinculos"]:
        contexto.definir_vinculo(VinculoAfetivo(
            dados["entidade_id"],
            dados["importancia"],
            dados["proximidade"],
            dados["responsabilidade"],
            dados["dependencia_operacional"],
            dados["familiaridade"],
            dados["confianca_operacional"],
        ))
    for dados in payload["expectativas"]:
        encerrada = dados.get("encerrada_com")
        contexto.adicionar_expectativa(Expectativa(
            dados["expectativa_id"],
            dados["entidade_id"],
            TipoExpectativa(dados["tipo"]),
            dados["criada_em"],
            dados["inicio_previsto_em"],
            dados["limite_em"],
            EstadoExpectativa(encerrada) if encerrada else None,
        ))
    for entidade_id, itens in payload["historico"].items():
        for dados in itens:
            if dados["entidade_id"] != entidade_id:
                raise ValueError("historico possui entidade_id inconsistente")
            contexto.registrar_experiencia(ExperienciaOperacional(
                dados["experiencia_id"],
                dados["entidade_id"],
                TipoExperienciaOperacional(dados["tipo"]),
                dados["ocorrido_em"],
            ))
    return contexto
