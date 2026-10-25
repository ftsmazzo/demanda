# API do Kanban (nucleo do produto)

Fluxo: mensagem do WhatsApp, depois contato, classificacao, demanda no quadro. Tudo isolado por tenant.

## Como as demandas nascem

`python -m app.cli classify-pending` classifica as mensagens novas e em seguida cria ou atualiza as demandas:

- uma mensagem entra na **demanda aberta do mesmo contato e setor**; sem demanda aberta, abre uma nova;
- "ok", "pode ser" e similares entram na demanda aberta mais recente do contato (nao viram ruido);
- demanda **concluida nunca e reaberta** por mensagem nova;
- ruido e mensagens enviadas pelo escritorio nao criam demanda;
- mensagens que a IA nao resolve vao para o setor **triagem**, com revisao.

## Configuracao (EasyPanel, servico `api`)

| Variavel | Para que serve |
|---|---|
| `JWT_SECRET` | **Obrigatoria para a API.** Minimo 32 caracteres aleatorios. Sem ela o login responde 503. |
| `TOKEN_TTL_MINUTES` | Opcional. Validade do token (1 a 1440, padrao 480). |

Gerar um segredo: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Criar usuarios

No console do `api` (a senha vem de `USER_PASSWORD` ou e pedida no terminal; nunca vai em argumento):

```bash
USER_PASSWORD='uma-senha-longa-123' python -m app.cli create-user --tenant-slug SLUG --email dono@exemplo.com --name "Nome" --role socio
python -m app.cli create-user --tenant-slug SLUG --email gestor@exemplo.com --name "Nome" --role gestor --sector fiscal --sector dp
```

Papeis e o que cada um ve:

| Papel | Ve | Altera |
|---|---|---|
| `socio` | tudo | tudo |
| `gestor` | demandas dos seus setores e as atribuidas a ele | tudo nelas; so cria e move para os seus setores |
| `colaborador` | so as atribuidas a ele | status e subtarefas |

`rh-interno` so aparece para socios e para quem tem esse setor, mesmo que a demanda seja atribuida a outra pessoa. Demandas que o usuario nao pode ver respondem **404**, como se nao existissem.

## Endpoints (`/api/v1`, exceto o login, com `Authorization: Bearer <token>`)

| Metodo e rota | Para que |
|---|---|
| `POST /auth/login` | `{tenant, email, password}` devolve o token |
| `GET /me` | perfil e setores do usuario |
| `GET /board` | quadro por status (`novo`, `em_andamento`, `aguardando`, `concluido`), com contagem por coluna; filtros `sector`, `assignee`, `closed_days` |
| `GET /demands` | lista com filtros `status`, `sector`, `urgency`, `assignee` (`me`, `none` ou id), `limit` (max 100), `offset` |
| `GET /demands/{id}` | detalhe: contato, responsavel, mensagens, subtarefas e progresso |
| `POST /demands` | cria demanda manual |
| `PATCH /demands/{id}` | altera titulo, status, urgencia, setor, prazo, responsavel |
| `POST /demands/{id}/subtasks`, `PATCH /subtasks/{id}` | checklist (ate 50 por demanda); o progresso e feito/total |
| `GET /contacts`, `PATCH /contacts/{id}` | socio e gestor: buscar e corrigir nome e tipo |
| `GET /users` | socio e gestor: usuarios ativos, para escolher responsavel |

Cada card traz `idle_hours` (horas desde a ultima movimentacao), a base para o alerta de demanda parada.

Exemplo:

```bash
curl -s -X POST https://demanda-api.kxryyk.easypanel.host/api/v1/auth/login -H 'Content-Type: application/json' -d '{"tenant":"SLUG","email":"dono@exemplo.com","password":"..."}'
curl -s https://demanda-api.kxryyk.easypanel.host/api/v1/board -H 'Authorization: Bearer TOKEN'
```

## Limitacoes conhecidas

- Nao ha interface web ainda; esta e so a API.
- Login: 5 falhas por conta bloqueiam por 10 minutos (em memoria, por processo); nao ha limite por IP. Convem limitar no proxy.
- Paginacao por `offset` (a ordem muda quando ha movimentacao); o quadro faz uma consulta por coluna, suficiente para o volume do piloto.
- Nao ha trilha de auditoria nem revogacao de token (a desativacao do usuario vale na hora, porque o usuario e relido a cada requisicao).
- O historico de mensagens anterior a migration vira demanda na primeira execucao do `classify-pending`.
