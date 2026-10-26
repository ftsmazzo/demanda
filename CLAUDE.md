# CLAUDE.md — Demanda

Fonte única de regras do projeto para agentes e desenvolvedores. Documentos de referência: `docs/PRD.md`, `docs/TRD.md`, `docs/simulacao-tenant-teste.md`.

## O que é

Plataforma multi-tenant que escuta o WhatsApp do escritório (Evolution API, somente leitura), classifica mensagens (regras + IA) em demandas, tarefas e compromissos por setor, e tem um agente que fala só com os sócios (resumo diário, alertas). MVP definido no PRD v0.2: 3 papéis fixos, painel de perfis na fase 2.

## Stack

Python + FastAPI, PostgreSQL 16 com RLS, fila no Postgres, React no frontend, Claude para IA, deploy no EasyPanel. Backend em `backend/`, interface em `frontend/` (Vite, React 18, TypeScript, Vitest, TanStack Query, dnd-kit), Dockerfile multi-estagio na raiz (o build do frontend vai para `/app/static` e a API o serve).

## Princípios de arquitetura

1. Gravar a mensagem bruta primeiro, processar depois. Idempotência por `(channel_id, provider_message_id)`.
2. Canal de WhatsApp, LLM e envio do agente ficam atrás de adaptadores (`MessageSender` etc.).
3. Números dos resumos vêm de SQL; a IA só classifica e redige.
4. Multi-tenant: toda tabela de negócio tem `tenant_id` e política RLS. O app não usa superusuário do banco.
5. Respostas curtas ("ok") em contato com demanda aberta anexam-se à demanda, nunca são descartadas.
6. Simplicidade vence sofisticação: o que é da fase 2 não entra no MVP.

## Checklist de segurança (verificar em todo PR)

- [ ] Nenhum segredo no repositório; só `.env.example` com placeholders.
- [ ] Toda consulta nova respeita `tenant_id` e RLS; há teste negativo de vazamento entre tenants.
- [ ] Webhooks validam a origem (chave/segredo) antes de gravar.
- [ ] Entrada de usuário validada com Pydantic; nada de SQL montado por concatenação.
- [ ] Autorização por papel e escopo aplicada na API, não só na interface.
- [ ] O que vai à IA é o mínimo necessário (texto e contexto curto).
- [ ] Alterações de demanda, usuário e regra passam pela auditoria.

## Fluxo de trabalho

- Trabalho rastreado em Issues do GitHub; uma branch por tarefa; PR pequeno para `main`.
- TDD no backend: teste primeiro, depois implementação.
- Revisão de código antes de mergear (`/ecc:code-review`).
- Decisões estruturais viram ADR em `docs/` (ver seção 8 do TRD).

## Esteira de qualidade (Python)

Ruff (lint e formato), pytest, e a CI do GitHub Actions (`.github/workflows/ci.yml`) rodam a cada PR. Adicionar tipos (mypy ou pyright) e detecção de código morto (vulture) quando houver código de negócio.

## Comandos

```bash
cd backend
pip install -r requirements-dev.txt
pytest
ruff check . && ruff format --check .
uvicorn app.main:app --reload
```

## Pendências de segurança abertas

- Repositório mantido **público** por decisão do responsável em 2026-10-24. Os docs têm estratégia de produto e nome de cliente piloto: tornar privado antes de inserir dados reais ou novos clientes. Nunca commitar segredos nem mensagens reais.
- Observabilidade (GlitchTip, Uptime Kuma) ainda não ligada.
- Runtime deve usar `APP_DATABASE_URL` (login `demanda_runtime`, sem privilegios). `DATABASE_URL` (dono do schema) so para migrations e CLI; nunca usar o dono em runtime.
- Sem rate limit no webhook (a cargo do proxy) e sem rotacao de segredo de canal.
- Toda migration nova precisa dar GRANT ao papel `demanda_app` nas tabelas que criar.
- O agente envia WhatsApp: manter `AGENT_SEND` desligado (ensaio) ate o responsavel conferir a caixa de saida; usar numero proprio da plataforma, nunca o do escritorio; so socios cadastrados recebem.
