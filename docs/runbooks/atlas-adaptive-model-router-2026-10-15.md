# Atlas: roteamento adaptativo com prioridade gratuita — 2026-10-15

## Objetivo e arquitetura

A configuração homologada do Hermes permanece com **1 modelo principal Nous e 12 fallbacks** (6 Nous e 6 NVIDIA). A nova camada é opt-in e possui dois caminhos complementares:

1. **Atlas inference router**: `GovernedInferenceRouter(adaptive_health=AdaptiveModelHealth(...))`, com integração opcional na fábrica OpenCode. O seletor original `select_free_models` é obrigatório **antes** do ranking adaptativo, incluindo autorização, compatibilidade de tarefa e preço zero verificado. Requisições com resultado incerto/timeout **nunca** são reexecutadas por outro modelo automaticamente.
2. **Hermes fallback**: `adaptive_hermes_order.py` consulta apenas os endpoints **GET** de catálogo Nous e NVIDIA, lê **metadados** de `~/.hermes/state.db` e reorganiza apenas os 12 fallbacks já revisados. Não altera `model.provider` nem `model.default` e não insere modelos novos. Consulte `config_hermes_free_fallback_expansion_2026-10-15.json` para a allowlist.

## Sinais e limites técnicos

- **Disponibilidade:** modelo presente no catálogo autenticado (não prova saúde do endpoint de inferência); modelo ausente recebe prioridade inferior e permanece na cadeia para recuperação. Falha ao consultar qualquer catálogo impede toda atualização.
- **Latência:** medida **por execução real** do roteador Atlas, armazenada em milissegundos; nenhuma medição é fabricada a partir de sessão longa do Hermes. São exigidas 3 amostras na ordenação Hermes. O timer não gera inferências pagas nem chamadas de chat.
- **Qualidade:** apenas avaliações externas com resultado booleano e pelo menos 3 casos distintos por modelo e tipo de tarefa. Na ausência de avaliações, fica neutra; contagem de uso não é medida de qualidade.
- **Quota/rate limit:** só aceita saldo explicitamente informado por telemetria; zero conhecido exclui o modelo do roteador Atlas. Erros 429 conhecidos acarretam cooldown temporário de uma hora. **Quota desconhecida não significa ilimitada.** O catálogo NVIDIA não fornece sozinho saldo ou cobrança efetiva. Na lista Hermes, modelos em cooldown são rebaixados, não apagados.
- **Aprendizagem:** SQLite privado com `signals` e `quality_evaluations`, sem prompts/respostas/chaves. Eventos com session_id são deduplicados e o banco antigo é migrado no lugar. Métricas de saúde têm TTL de 24h; avaliações de qualidade, 30 dias.
- **Fonte Hermes:** tabela `session_model_usage` em SQLite aberta em read-only, agregada em janela de 7 dias. Uso recente é apenas critério de desempate com >=3 chamadas, não prova de sucesso.
- **Custo:** modelos Nous `:free` e protótipos NVIDIA previamente homologados por chamadas reais. **Preço efetivamente cobrado pela NVIDIA ainda é desconhecido**, portanto o escalonamento automático mantém Nous à frente de NVIDIA, sujeito a cotas e condições do provedor.

## Implantação em pentium

Código instalado isoladamente em `~/.local/share/atlas-adaptive-router/infrastructure/pentium/atlas/`. Unidade de usuário instalada em `~/.config/systemd/user/atlas-hermes-adaptive.service` e timer instalado em `~/.config/systemd/user/atlas-hermes-adaptive.timer`. `Linger=yes` já verificado.

Validação somente de leitura realizada a partir do diretório instalado: `ADAPTIVE_FALLBACK {'candidates': 12, 'catalog_nous': 7, 'catalog_nvidia': 80, 'changed': False, 'apply': False}`.

**Atenção — ativação pendente:** o comando de inicialização do serviço foi bloqueado pelas configurações de segurança da ferramenta remota. Os arquivos estão instalados e o serviço foi verificado como `inactive`; o timer foi verificado como `disabled`. Portanto não anunciar agendamento ativo sem execução manual. Para habilitar no próprio terminal do pentium, após conferir o código:

```bash
systemctl --user enable --now atlas-hermes-adaptive.timer
systemctl --user start atlas-hermes-adaptive.service
systemctl --user status atlas-hermes-adaptive.service --no-pager
systemctl --user list-timers atlas-hermes-adaptive.timer
hermes fallback list
```

A rotina executa **a cada aproximadamente seis horas**, além do disparo pós-boot, com atraso aleatório para não concentrar cargas. Se offline, não altera o arquivo Hermes e poderá tentar no próximo timer. A rotina salva backup com modo 0600 e confere se o YAML não mudou entre a leitura e a escrita. Nunca publicar `~/.hermes/config.yaml` ou `~/.hermes/auth.json` no Git.

## Homologação realizada / próxima gate

- Windows: testes de qualidade, cooldown, compatibilidade de schema, fail-closed e regressão do roteador. Linux: testes equivalentes. Ver resultados no checkpoint.
- API de catálogos validada no pentium (7 recomendações Nous `:free`, 80 IDs NVIDIA). Configuração permanece estável sem reordenação arbitrária.
- **Ainda não homologado:** monitoramento real de quota restante da NVIDIA, benchmark independente de qualidade por tarefa, feed de latência do processo Hermes diretamente, teste de falha forçada E2E de toda a cadeia e ativação do timer systemd.
- O OpenCode remoto usa infraestrutura separada e ainda não substitui o daemon Hermes.
