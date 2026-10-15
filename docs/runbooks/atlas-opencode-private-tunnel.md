# OpenCode remoto do Atlas — transporte privado

O daemon do Atlas no `pentium` permanece no Hermes por padrão. Para disponibilizar OpenCode, use o túnel SSH **somente em loopback** `127.0.0.1:49375` → `x99:127.0.0.1:49374`. O servidor HTTP OpenCode continua exigindo autenticação Basic, separada da autenticação SSH. Não copie senhas ou tokens para o Git.

O serviço de usuário `opencode-x99-tunnel.service` está incluído como configuração, mas não é habilitado automaticamente. Verifique o SSH host key e o preflight antes de usar. Quando a API retornar 401 sem credenciais, o túnel está alcançando um endpoint autenticado; isso não significa que a inferência está pronta. O runtime exige ainda credencial protegida no pentium, ofertas de custo zero verificadas, allowlist e teste de inferência real. Nunca use o túnel público `opentunnel` como backend do Atlas.

Não habilite o backend OpenCode por substituição automática do Hermes; use `inference_backend_factory` explicitamente após homologação. A ausência de credencial, falha de túnel, custo desconhecido ou resultado incerto devem interromper a inferência sem retry ambíguo.
