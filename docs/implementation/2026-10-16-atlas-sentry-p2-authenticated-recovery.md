# Atlas — CP-SENTRY-P2: recuperação autenticada em dois domínios

Data: 2026-10-16
Estado: **biblioteca e testes implementados no x99; deploy em HOLD**
Dependência: CP-SENTRY-P0 `8cc77ad` e CP-SENTRY-P1 `efc7ba8`

## Problema resolvido neste checkpoint

Antes do P2, `FailureMemory.record_verified_lesson()` recebia um callback
injetado. Essa interface P0 é útil para testes, mas não comprova a origem do
resultado: um callback complacente poderia declarar `True`.

O P2 implementa o fluxo seguro `learn_from_authenticated_recovery()`,
um gate adicional com validação de **três recibos com HMAC-SHA256**:

1. `executor`: atesta autorização por política e sucesso de uma operação
   de serviço previamente permitida (`restart_service`, `start_service`).
2. `health_probe`: primeira observação HEALTHY, feita por um produtor
   diferente do executor.
3. `health_probe`: segunda observação HEALTHY posterior, com outra
   evidência distinta.

Os recibos têm esquema estrito e autenticam: `incident_id`, `component`,
`host`, `target`, `action_id`, `receipt_id`, `event_at`,
`operation`, `authorized`, `status`, `evidence_ref`, `issuer`,
`key_id` e versão. Nenhum desses campos é aceito fora da assinatura.

**Validação obrigatória:**

- HMAC em JSON canônico e comparação constante, esquema exato, tamanho
  limitado (2 KiB), timestamps UTC com timezone, rejeição a assinaturas
  modificadas, keys desconhecidas, replay cruzado e recibos duplicados.
- Dois segredos de no mínimo 256 bits, diferentes entre os dois domínios;
  rotação controlada por `key_id`. Os testes usam chaves artificiais.
- `trusted_host` configurado explicitamente e mesmo host/target/incidente
  nos três recibos. O incidente deve estar em `recovered` com pelo menos
  duas observações HEALTHY.
- `opened_at <= action_at < probe_1_at < probe_2_at <= resolved_at <= now`
  e janela máxima de frescor de 24 horas por padrão.
- IDs de evidência dos dois probes devem ser **diferentes** e estar presentes
  em `recovery_evidence_refs` do incidente persistido.
- Mesmo `action_id` nos três recibos, ligando observações à correção
  específica. Reutilizar recibos para outro incidente, host ou ação falha.
- Um incidente com componente `inference.*` não pode ser validado por
  `restart_service`: falhas de modelo exigem outra política de evidência.
- Falhas do verificador são fail-closed. Nada é aprendido se a verificação
  faltar ou falhar; o Sentry nunca executa comandos nem concede permissões.

## Arquivos

- `infrastructure/pentium/atlas/sentry_recovery_verifier.py`
- `infrastructure/pentium/atlas/tests/test_sentry_recovery_verifier.py`
- Este relatório.

Esta implementação usa somente a biblioteca padrão Python. Nenhuma
credencial de produção foi gerada, guardada ou colocada em Git.

## Limites técnicos e modelo de confiança

**HMAC é autenticação por segredo compartilhado, não assinatura assimétrica.**
Os emissores `executor` e `health_probe` precisam ser executados em
identidades/processos isolados, com segredos próprios e provisionamento via
secret manager/credencial segura fora de prompts, variáveis publicadas, logs
ou repositórios. O consumidor com acesso aos dois segredos também seria
capaz de forjar recibos caso fosse comprometido; portanto a separação de
processos, ACL e monitoramento continuam obrigatórios. Para isolamento
criptográfico unilateral, o próximo endurecimento pode migrar para
assinaturas assimétricas Ed25519, mantendo `key_id` e esquema versionado.

O helper `sign_recovery_receipt` **é API do emissor confiável**, nunca
capability dos agentes, nem texto de contexto da LLM. O código garante
autenticidade dos eventos apresentados; não garante por si só que os
emissores produziram verificações reais. A obtenção dos recibos
com controle de ACL e a integração com os serviços autorizados ainda
precisam ser realizadas em ambiente de homologação.

**P0 legada:** `record_verified_lesson(..., verifier=callable)` continua
disponível por compatibilidade e tests. Não existe caminho de criação de
lições automático conectado no Pentium. A recomendação operacional é
expor SOMENTE `learn_from_authenticated_recovery` no serviço de ingestão
confiável, após bloquear rotas legadas e verificar a identidade dos emissores.

**Evidência de probe por execução:** o supervisor atual às vezes agrega
refs estáticas, como `probe:healthy`. Para P2 em produção, o emissor
precisará criar IDs únicos por leitura para atestar dois ciclos físicos
distintos. Sem isso o gate rejeita o aprendizado, como desejado.

**Sem promoção cognitiva:** lições continuam em FailureMemory isolado,
read-only `authority=evidence_only`; não viram instruções permanentes
nem elevam privilégios de agentes.

## TDD / regressão

```powershell
cd C:\Users\deral\DevEx-HomeLab
py -m unittest infrastructure.pentium.atlas.tests.test_sentry_recovery_verifier -q
py -m pytest -q infrastructure/pentium/atlas/tests --disable-warnings --maxfail=1
```

**Resultado executado no x99:** 18 testes focados do verificador passaram. Na regressão integral do Atlas: **1349 passed, 4 skipped, 213 subtests passed em 37.00s**, processo com exit code 0. Foi necessário corrigir separadamente um teste untracked preexistente do `SelfWorkRuntime` que tentava executar dois `recover()` consecutivos sem `begin_retry()`. O método `begin_retry()` foi adicionalmente protegido contra chamadas fora do estado `RECOVERING` e contra TTL vencido; ambas as alterações pertencem a uma árvore de trabalho anterior e **não compõem este commit P2**.

Testes TDD: casos válidos, ausência de recovery, sem segundo probe,
alterações após assinatura, HMAC de papel diferente, key id desconhecido,
replay cruzado, duplicação, tempos fora de ordem, autorização falsa,
instrução injetada, recibos enormes, correlação de ação/host,
comprovação na evidência do supervisor e falhas de fornecedor.

## Gates ainda necessários para produção (sem atestado de 100%)

1. Signers reais em principal isolado: um no executor autorizado, outro
   no supervisor/probe, sem disponibilizar segredos à LLM ou agentes.
2. Canal de ingestão autenticado, retenção auditável dos recibos assinados
   e mecanismo de revogação/rotação de chaves; proteger contra concorrência
   e incidentes antigos.
3. Correlação do `action_id` com o plano/autorização original, eventos
   de serviço físico e snapshots com evidências únicas, não só status.
4. Homologação em Pentium/Core/x99: canary, backup, rollback, perda de energia,
   erro de disco, segurança multi-processo e testes de falha no emissor.
5. Gate separado para falhas da rota Hermes/OpenCode, sem confundir
   saúde de serviço com sucesso semântico da resposta da LLM.

O checkpoint de validação de recibos pode ficar GREEN localmente sem
habilitar autonomia corretiva no runtime real.
