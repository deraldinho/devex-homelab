# Atlas C3 — Reaction Loop Implementation Plan

**Goal:** ligar C1 e C2 em um loop cognitivo determinístico, bounded e sem autoridade operacional.

**Base:** C2 certificado no SHA `557104c1c5bed67ce39ec4704889600b81af727c`.

**Scope:**
- criar modelos de entrada/saída do Reaction Loop;
- avaliar ActivationPolicy antes de qualquer inferência;
- construir `ContextoCognitivo` somente quando ativado;
- chamar `LLMGateway` somente com esse contexto;
- converter sucesso/erro do gateway em `RespostaCognitiva` estruturada;
- fallback sem mutar estado técnico/afetivo;
- empacotar e adicionar marker C3 no CI.

**Out of scope:** C4 capability policy, execução de comandos, deploy físico, modelo real obrigatório.
