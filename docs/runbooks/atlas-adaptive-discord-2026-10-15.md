# Atlas: monitoramento de modelos e Discord nativo — 2026-10-15

A arquitetura mantém **Hermes como pool de agentes/mentes** e o `atlas-discord.service` como único gateway Discord do Atlas. Não utiliza `hermes send`, tokens ou integração Discord do Hermes.

## Operação

- Timer de usuário `atlas-hermes-adaptive.timer`: `OnUnitInactiveSec=5min`, variação até 30 segundos, disparo inicial pós-boot em 2 minutos.
- Serviço `atlas-hermes-adaptive.service`: verifica catálogos atuais Nous/NVIDIA usando somente GET, preserva o modelo principal e os 12 fallbacks; reorganiza apenas se necessário.
- Relatórios usam a fila **nativa do Atlas** `~/pentium-agent/atlas/runtime/discord-action-queue.jsonl`, capacidade `discord_send_alert`, canal padrão configurado como `alert_channel_id` no gateway.
- Estado de deduplicação em `adaptive-model-report-state.json`. Sem alterações: resumo a cada aproximadamente 60 minutos. Mudança do número de candidatos/contagem de catálogos ou reordenação: alerta imediato na próxima execução.
- Não são gravados segredos, prompts nem respostas. Não são executadas inferências durante a verificação periódica.
- Relatórios são enfileirados somente após uma execução de catálogo bem-sucedida. Falha de consulta impede aplicação e não gera afirmações falsas sobre disponibilidade.
- **Limitação conhecida:** o consumido pelo gateway não comprova confirmação visual no Discord; confirmar pela interface do canal quando necessário.

## Validação real no pentium

- Gateway `atlas-discord.service` ativo, health `connected=true`, canal de alertas configurado.
- `systemctl --user list-timers atlas-hermes-adaptive.timer` demonstrou próxima execução em **2026-10-15 08:52:27 -03** após a última às 08:46:58.
- Journald: 08:46:59 `ADAPTIVE_FALLBACK candidates=12 catalog_nous=7 catalog_nvidia=80 changed=False` e `ATLAS_DISCORD_QUEUED True`; 08:47:17 uma reexecução marcou `ATLAS_DISCORD_QUEUED False` por deduplicação.
- Fila: `items=3`, `consumer_cursor=3`, uma nova mensagem adaptativa e `latest_adaptive_consumed=True`.
- Nova rotina de relatórios tem testes de deduplicação e validação de payload. Ajustes da interface obedecem ao pipeline de deploy separado do daemon Atlas; a integração reutiliza a fila já reconhecida.

## Verificações

```bash
systemctl --user list-timers atlas-hermes-adaptive.timer
journalctl --user -u atlas-hermes-adaptive.service -n 20 --no-pager
systemctl --user is-active atlas-discord.service
```

**Limites:** a lista de modelos disponíveis não comprova quota restante nem custo real de inferência; endpoints NVIDIA permanecem de prototipagem e sujeitos a limite do provedor.
