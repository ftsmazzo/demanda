# TRD — Demanda

> Technical Requirements Document — como construir. Alinhado ao PRD v0.2 (recorte de MVP).
> **Versão 0.1 (rascunho).** Itens `[SUGESTÃO]` são o padrão recomendado e devem ser confirmados ou trocados, de preferência pela stack do Prumo para reaproveitar código e conhecimento.

**Data**: 2026-10-24
**Responsável**: Fábrica dos Dados

## 1. Princípios

1. **Entregar o MVP medindo.** Cada etapa produz algo usável e mensurável.
2. **Base sólida, camadas finas.** Multi-tenant e catálogo de permissões nascem no modelo; a interface avançada vem depois.
3. **Trocável por adaptadores.** Canal de WhatsApp, LLM e envio do agente ficam atrás de interfaces.
4. **Determinístico onde dá.** Números dos resumos vêm de consultas ao banco. A IA só classifica e redige.
5. **Nunca perder mensagem.** Gravar o bruto primeiro, processar depois.

## 2. Visão geral da arquitetura

```
WhatsApp do escritório
        |
   Evolution API  --webhook-->  Ingestão (idempotente)
                                      |
                                messages (bruto, no banco)
                                      |
                                 Fila de jobs
                                      |
                  Classificador: regras -> LLM -> confiança
                                      |
              demandas / tarefas / compromissos / contatos
                                      |
           API  <-->  Web (Kanban, tarefas, agenda, painel)
                                      |
        Agendador do agente --> MessageSender --> sócios (WhatsApp)
```

## 3. Stack `[SUGESTÃO]`

| Camada | Escolha | Motivo |
|---|---|---|
| Banco | PostgreSQL 16 com RLS | Isolamento por tenant no próprio banco; JSONB para payloads |
| Backend | Python + FastAPI (async) | Rápido de evoluir, bom para IA; reaproveita o conhecimento do time |
| Fila e jobs | Fila no próprio Postgres (ex. Procrastinate) | Um serviço a menos que Redis; suficiente para o volume |
| Frontend | React (Vite ou Next) + Tailwind; Kanban com dnd-kit | Web responsivo, ecossistema maduro |
| IA | Claude: modelo leve para classificar, modelo maior para redigir resumos | Custo baixo na classificação, qualidade no texto |
| WhatsApp (escuta) | Evolution API, como no Prumo | Experiência prévia sem problemas |
| Deploy | EasyPanel, serviços isolados (app, worker, banco, Evolution) | Padrão da Fábrica |
| Observabilidade | GlitchTip (erros) e Uptime Kuma (`/health`) | Self-hosted, grátis, compatível com EasyPanel |

Se o Prumo usa outra stack (por exemplo Node), vale seguir a mesma. A arquitetura acima não depende da linguagem.

## 4. Modelo de dados (principais tabelas)

Toda tabela de negócio tem `tenant_id` e política RLS.

| Tabela | Papel |
|---|---|
| `tenants` | Empresas (slug, fuso, horário comercial, configurações) |
| `users`, `user_sectors` | Usuários, papel fixo no MVP, setores a que pertencem |
| `permissions`, `role_permissions` | Catálogo fixo de permissões e vínculo por papel (a interface liga/desliga é a fase 2) |
| `sectors` | Setores do tenant |
| `channels` | Origens de mensagem (instância Evolution, setor padrão, estado de saúde) |
| `contacts`, `contact_sectors` | Números que interagem: tipo (cliente, fornecedor, colaborador) e setores que os atendem |
| `messages` | Mensagem bruta: canal, id do provedor, direção, tipo, texto, mídia, datas |
| `message_events` | Edição e exclusão como eventos, sem sobrescrever o original |
| `conversations` | Agrupa mensagens por contato e janela de tempo |
| `demands` | Demanda/tarefa: setor, tipo, urgência, status, responsável, prazo, progresso, origem do "dono" (regra, IA ou humano) |
| `demand_messages` | Liga mensagens à demanda (uma demanda pode ter várias mensagens, e vice-versa) |
| `subtasks` | Itens da barra de progresso |
| `appointments` | Compromissos, participantes e confirmação |
| `routing_rules` | Regras versionadas de roteamento |
| `classification_events` | Quem classificou (regra, IA, humano), confiança, versão da regra/prompt, correções |
| `agent_recipients` | Sócios que recebem o agente, telefone e vínculo ao tenant |
| `agent_notifications` | Alertas e resumos gerados e enviados (evita duplicidade) |
| `holidays` | Feriados para o cálculo de dias úteis |
| `audit_log` | Quem alterou o quê |

Restrição-chave de idempotência: `UNIQUE (channel_id, provider_message_id)` em `messages`.

## 5. Ingestão e confiabilidade

- O webhook só valida, grava o bruto em `messages` e enfileira. Responde rápido.
- Duplicados são ignorados pela restrição única. Mensagens fora de ordem são ordenadas pelo horário do provedor.
- Edição e exclusão viram `message_events`.
- Fila com retry e backoff, e fila de falhas (DLQ) visível para o administrador.
- **Reconciliação periódica:** um job busca na Evolution as mensagens recentes e preenche lacunas.
- **Saúde da instância:** checagem a cada minuto, estado em `channels`; queda gera alerta aos sócios e ao GlitchTip.
- Áudio, imagem e documento: o MVP guarda a mídia e o metadado e marca "conteúdo não lido". Transcrição e visão entram na fase 2.
- Grupos: configuráveis por canal (ouvir ou ignorar). Padrão: só conversas diretas, a confirmar no piloto.

## 6. Classificação

1. **Regras determinísticas** (palavras, canal, contato já vinculado a setor) rodam primeiro.
2. **LLM** recebe o texto, as últimas mensagens da conversa, o tipo de contato e o histórico de setor, e devolve JSON estruturado: setor, tipo, urgência, cliente, confiança e se é ruído.
3. **Limiares:** confiança abaixo do corte vai para `triagem` e para a fila de não classificadas.
4. **Respostas curtas** ("ok", "pode ser") em contato com demanda aberta anexam-se à demanda e nunca são descartadas.
5. **Correção humana** em um clique grava um `classification_event`, vira exemplo para o prompt e pode gerar uma regra.
6. **Versionamento:** regras e prompts têm versão. É possível reprocessar um período e comparar.
7. **Custo:** modelo leve, cache por conteúdo, limite mensal por tenant com alerta.
8. **Minimização:** vai à IA só o texto necessário e o contexto curto; sem anexos no MVP.

## 7. Agente dos sócios

- **Agendador** por tenant, no fuso do tenant, com cálculo de dias úteis (`holidays`) e horário de silêncio.
- **Tipos:** resumo diário (18:00), alerta de pendências paradas (consolidado às 09:00) e alerta crítico (imediato).
- **Conteúdo:** números vêm de consultas SQL; a IA só redige o texto a partir de dados já calculados.
- **Idempotência:** `agent_notifications` impede alerta duplicado e permite reenvio seguro.
- **Interação:** o sócio pode perguntar ("o que está parado no fiscal?") e pedir cobrança. A IA responde sobre dados reais, com ferramentas de leitura restritas ao tenant.
- **Identificação do tenant:** o telefone de `agent_recipients` resolve o tenant. Se o mesmo telefone existir em mais de um tenant, o agente pergunta "de qual empresa?" e guarda o tenant ativo por um tempo limitado. Telefone desconhecido é ignorado, com pedido opcional de código de pareamento.

## 8. ADRs (decisões e gatilhos de revisão)

| ADR | Decisão | Motivo | Quando rever |
|---|---|---|---|
| 001 | **Envio do agente via adaptador `MessageSender`.** No MVP, uma instância Evolution dedicada ao número do agente. | Baixo volume, só sócios, e os sócios iniciam conversa. Não bloqueia o projeto. | Banimento do número, ou mais de 3 tenants: trocar para a API oficial da Meta (templates aprovados e janela de 24h) sem mexer no resto. |
| 002 | **Escuta pela Evolution, só leitura, com reconciliação.** | Funciona no Prumo. | Perdas acima do aceitável no piloto. |
| 003 | **Multi-tenant por `tenant_id` + RLS**, com papel de banco sem superusuário e teste de vazamento entre tenants. | Retrofit é caro. | Nunca (decisão estrutural). |
| 004 | **Permissões por catálogo fixo + vínculo ao papel.** MVP com 3 papéis. | A interface liga/desliga vira só UI na fase 2. | Quando a fase 2 começar. |
| 005 | **Retenção:** manter por padrão, configurável por tenant. Mínimo necessário vai à IA. | Contexto de baixo sigilo; evitar peso desnecessário. | Novos clientes ou contratos que exijam outra regra. |
| 006 | **Fila no Postgres.** | Menos infraestrutura. | Volume que exija Redis ou outro broker. |

## 9. Segurança

- Autenticação por e-mail e senha (hash forte) ou link mágico; sessão com expiração. `[SUGESTÃO]`
- Autorização por papel + escopo (sócio: tudo; gestor: seu setor; colaborador: o que é seu), aplicada na API e reforçada pelo RLS.
- Segredos só em variáveis de ambiente do EasyPanel; nada no repositório.
- Mídia em armazenamento privado com URLs temporárias.
- Backups diários do Postgres com teste de restauração.
- Auditoria leve em alterações de demanda, usuário e regra.

## 10. Requisitos não funcionais

| Item | Meta do MVP |
|---|---|
| Volume | Centenas de mensagens por dia, ~15 usuários por tenant |
| Disponibilidade | Boa, sem alta disponibilidade; recuperação em horas |
| Latência | Mensagem aparece classificada em menos de 1 minuto |
| Custo de IA | Medido por tenant, com teto mensal |
| Manutenção | Time pequeno da Fábrica; simplicidade vence sofisticação |

## 11. Qualidade e testes

- **TDD** no backend; testes de integração com Postgres real.
- **Testes de isolamento (negativos)** a partir da seção 10 da simulação: perfil contra perfil, tenant contra tenant, telefone desconhecido, mesmo telefone em dois tenants. Cobrem API, consultas, busca e notificações.
- **Conjunto de mensagens rotuladas:** começa com o dia da simulação e cresce com as correções do piloto. Um script mede acerto por campo (setor, tipo, urgência, cliente).
- **Teste do pipeline:** mensagens duplicadas, fora de ordem, editadas e apagadas.
- **E2E** dos fluxos principais: mensagem chega, vira demanda, aparece no Kanban, entra no resumo.
- **Esteira:** formatação e lint (Ruff), tipos, detecção de código morto, testes e revisão de código a cada PR. `[SUGESTÃO]` para stack Python.

## 12. Plano técnico inicial (spikes)

| Spike | Objetivo | Duração |
|---|---|---|
| 1 | Evolution, webhook, Postgres, idempotência e reconciliação, com mensagens reais do piloto | 2 a 3 dias |
| 2 | Classificação de ~200 mensagens (reais anonimizadas ou simuladas): acerto, custo por mensagem, latência | 2 a 3 dias |
| 3 | Agente: resumo diário a partir de dados reais e envio por `MessageSender` | 1 a 2 dias |

## 13. Pendências para confirmar

1. A stack sugerida, ou a do Prumo?
2. A instância Evolution do piloto: reaproveitar o servidor do Prumo ou criar uma nova?
3. Provedor e modelos de IA (sugestão: Claude, com modelo leve na classificação).
4. Quem recebe a conta e o limite de custo de IA do piloto?
