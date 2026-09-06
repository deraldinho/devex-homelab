# Atlas K2 — Prefix/KV Cache residente

## Objetivo

Reduzir custo de prompt da mini LLM mantendo `llama-server` residente e reutilizando KV/prefix cache local, sem alterar ownership cognitivo nem abrir listener TCP.

## Architecture & Business Rules Check

- K1 continua responsável por reutilização de resposta exata.
- K2 atua somente dentro do backend LLM; não decide ativação, memória, estado ou capability.
- Transporte é Unix socket local; nenhuma porta TCP é aberta.
- O processo servidor recebe argv fixo, `shell=False` e modelo local já provisionado.
- Falha do runtime residente deve degradar para o backend CLI existente.
- Nenhum slot/KV cache é persistido em disco no K2.
- O contexto continua bounded pelo `LLMGateway`; K2 não amplia prompt nem saída.
- Mudança de modelo/configuração invalida o runtime por reinicialização, não por reutilização silenciosa.