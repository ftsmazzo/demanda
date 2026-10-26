# API do Kanban (nucleo do produto)

Fluxo: mensagem do WhatsApp, depois contato, classificacao, demanda no quadro. Tudo isolado por tenant.

## Como as demandas nascem

`python -m app.cli classify-pending` classifica as mensagens novas e em seguida cria ou atualiza as demandas:

- uma mensagem entra na **demanda aberta do mesmo contato e setor**; sem demanda aberta, abre uma nova;
- "ok", "pode ser" e similares entram na demanda aberta mais recente do contato (nao viram ruido);
- demanda **concluida nunca e reaberta** por mensagem nova;
- ruido e mensagens enviadas pelo escritorio nao criam demanda;
- mensagens que a IA nao resolve vao para o setor **triagem**, com revisao.

## Ver o quadro sem a API

```bash
python -m app.cli classify-pending --no-llm        # classifica e cria as demandas
python -m app.cli demands --tenant-slug SLUG       # quadro em texto
python -m app.cli demands --tenant-slug SLUG --open --limit 100
```

Cada linha: `[status] setor/urgencia tipo | contato ...final do telefone | parada ha Nh | titulo`.

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

## Processamento automatico

Com `WORKER_INTERVAL_SECONDS` (por exemplo `30`) a propria API roda um ciclo em segundo plano: classifica as mensagens novas (regras e, se houver chave, IA) e abre ou atualiza as demandas de cada tenant. Sem a variavel, so o `classify-pending` manual faz isso. Use uma unica replica da API.

## Monitor da Evolution

Com `EVOLUTION_URL` e `EVOLUTION_API_KEY` (e, opcionalmente, `HEALTH_INTERVAL_SECONDS`, padrao 60) a API consulta `GET /instance/connectionState/{instancia}` de cada canal e grava o estado em `channels.health_state`. Estando `open`, busca em `POST /chat/findMessages/{instancia}` as mensagens da janela desde a ultima reconciliacao (menos 10 min de folga; 24 h na primeira vez; no maximo 72 h) e grava as que o webhook nao entregou, sem duplicar. Quando o estado deixa de ser `open`, o log registra erro e a interface mostra um aviso aos socios e gestores (`GET /api/v1/channels/health`). A chave nunca vai ao navegador.

## Agente dos socios

Liga com `AGENT_INSTANCE` (instancia da Evolution com o numero da plataforma, diferente da instancia que escuta o escritorio), alem de `EVOLUTION_URL` e `EVOLUTION_API_KEY`. Fala so com os destinatarios cadastrados (`add-recipient`, que aceita apenas socio como usuario ligado). Tres avisos, todos de segunda a sexta quando indicado e so entre 07h e 21h na hora do escritorio:

- compromisso novo proposto (nas ultimas 24 h), com link para a Agenda;
- resumo do dia a partir das 18h: novas, concluidas, abertas, criticas, as mais paradas e os compromissos de amanha;
- demandas paradas ha 72 h ou mais, a partir das 9h (so quando ha alguma).

Os numeros vem de consultas SQL e o texto e montado por modelos: a IA nao escreve nada que va ao socio. Cada aviso tem chave de idempotencia por pessoa (`agent_notifications`), tenta ate 3 vezes (espera de 5 min) e no maximo 12 por pessoa em 24 h.

Sem `AGENT_SEND=1` o agente trabalha em **ensaio**: grava o texto e marca `dry_run`, sem enviar. Veja o que ele diria com `python -m app.cli agent-outbox --tenant-slug SLUG`. Cadastro: `add-recipient --tenant-slug SLUG --name NOME --phone 5511999990101 [--user-email EMAIL]`, `recipients`, `remove-recipient`.

### Respostas pelo WhatsApp

Com `AGENT_WEBHOOK_SECRET`, a instancia do agente passa a enviar suas mensagens recebidas para `POST /webhooks/agent` (evento `MESSAGES_UPSERT`, cabecalho `X-Webhook-Secret`). Quem escreve e identificado pelo telefone: so destinatarios cadastrados sao atendidos; numero desconhecido ou cadastrado em mais de uma empresa e ignorado em silencio. Comandos: `1` confirma e `2` cancela o compromisso mais recente ainda proposto que o agente avisou; `parado`/`pendencias` lista as demandas paradas ha 24 h ou mais; `agenda` mostra hoje e amanha; `ajuda` explica. Qualquer outro texto recebe "nao entendi" e nada e alterado (confirmar so vale com a palavra ou o numero sozinhos). Cada resposta e registrada na caixa de saida (`kind reply`), uma por mensagem recebida, no maximo 60 por pessoa em 24 h.

## Limitacoes conhecidas

- A interface web (`frontend/`) e servida pela propria API a partir de `STATIC_DIR` (a imagem Docker ja a embute em `/app/static`). Mesma origem, sem CORS.
- Login: 5 falhas por conta bloqueiam por 10 minutos (em memoria, por processo); nao ha limite por IP. Convem limitar no proxy.
- Paginacao por `offset` (a ordem muda quando ha movimentacao); o quadro faz uma consulta por coluna, suficiente para o volume do piloto.
- Nao ha trilha de auditoria nem revogacao de token (a desativacao do usuario vale na hora, porque o usuario e relido a cada requisicao).
- O historico de mensagens anterior a migration vira demanda na primeira execucao do `classify-pending`.
