# Spike 1: ingestao do WhatsApp via Evolution

Objetivo: receber mensagens reais pelo webhook da Evolution, gravar no Postgres sem perder nem duplicar, e medir perda e latencia (TRD, secao 12).

## O que ja existe

- `POST /webhooks/evolution/{channel_id}`: autentica pelo cabecalho `X-Webhook-Secret`, grava a mensagem bruta e responde `{received, stored, duplicates, ignored}`.
- Idempotencia: `UNIQUE (channel_id, provider_message_id)` com `ON CONFLICT DO NOTHING`. Reentrega nao duplica.
- Isolamento: RLS por `app.tenant_id`. Em runtime a aplicacao conecta com o login `demanda_runtime` (sem privilegios proprios), que so consegue assumir o papel `demanda_app`.
- Mensagens recebidas e enviadas pelo escritorio sao gravadas (`direction` in/out). Grupos, status, reacoes e eventos de protocolo sao descartados (grupos podem ser ligados por canal).
- Protecoes: corpo limitado (padrao 2 MB, 413 acima), NUL e blobs base64 removidos antes de gravar, pool com timeout curto (503 quando esgotado), `/docs` desligado.
- `GET /health` (vivo) e `GET /health/ready` (banco).

## Variaveis de ambiente do servico `api`

| Variavel | Para que serve |
|---|---|
| `DATABASE_URL` | Conexao do dono do schema. So migrations e CLI. |
| `APP_DB_PASSWORD` | Senha do login `demanda_runtime`; criado na subida quando `AUTO_MIGRATE=1`. |
| `APP_DATABASE_URL` | Conexao de runtime: mesmo host e banco, usuario `demanda_runtime` e a senha acima. |
| `AUTO_MIGRATE` | `1` aplica as migrations e provisiona o login de runtime na subida. |
| `MAX_BODY_BYTES`, `DB_POOL_MAX` | Opcionais (padroes 2000000 e 5). |

## Como ligar a Evolution

1. Com as variaveis acima definidas e o servico reimplantado, crie o tenant e o canal no console do servico `api` (EasyPanel). O segredo aparece uma unica vez:

```bash
python -m app.cli create-tenant --slug contabilidade-piloto --name "Contabilidade Piloto"
python -m app.cli create-channel --tenant-slug contabilidade-piloto --name "WhatsApp do escritorio" --instance NOME_DA_INSTANCIA
```

2. Na instancia da Evolution, configure o webhook:
   - URL: `https://demanda-api.kxryyk.easypanel.host/webhooks/evolution/<channel_id>`
   - Evento: `MESSAGES_UPSERT`
   - Cabecalho: `X-Webhook-Secret: <segredo>`
   - Deixe desligada a opcao de enviar midia em base64 no webhook.
3. Envie uma mensagem de teste e confira em `messages`.

## Como medir (criterios do spike)

| Medida | Como |
|---|---|
| Perda | Comparar o total no celular com `count(*)` por dia em `messages`. |
| Duplicidade | Deve ser zero por construcao; `duplicates` na resposta mostra reentregas. |
| Latencia | `received_at - provider_timestamp` em `messages`. |

## Fora deste passo (proximos)

- Reconciliacao periodica buscando mensagens recentes na Evolution (preenche lacunas).
- Monitor de saude da instancia e alerta de queda.
- Edicao e exclusao de mensagens como eventos.
- Rate limit por IP e canal (hoje fica a cargo do proxy) e rotacao de segredo do canal.
- Checksum das migrations ja aplicadas.
