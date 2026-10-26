# Agente em linguagem natural

O socio escreve para a Secretaria como falaria com uma pessoa ("o que a Ana tem pendente?", "cria uma tarefa para o Bruno: conferir a folha do Mercado Bom Preco", "marca a Padaria como prioritaria", "remarca a reuniao do projeto pra quinta as 15h"). Os comandos curtos (`1`, `2`, `parado`, `agenda`, `ajuda`) continuam valendo e nao gastam IA.

## Principios

- **A IA so entende o pedido** (qual e a intencao e quais sao os dados citados). Quem consulta o banco, resolve nomes, faz contas de data e monta a resposta e o codigo: numeros vem de SQL.
- **Consulta responde na hora; alteracao pede confirmacao.** Criar tarefa, atribuir, mudar situacao e marcar prioridade viram uma proposta ("Vou criar a tarefa X para Y. Responda 1 para confirmar ou 2 para cancelar") guardada em `agent_pending_actions` por 15 minutos. So o `1` executa.
- **Nome ambiguo nao adivinha.** Se mais de uma pessoa, cliente ou demanda combina, o agente lista as opcoes e pede para repetir com mais detalhe.
- Falha da IA, teto diario (`AGENT_NL_DAILY_CAP`) ou IA desligada: o agente responde "Nao entendi" como antes.
- Tudo o que o socio muda fica no historico do caso (`case_events`, ator `user`).

## Intencoes

`query_demands` (filtros: situacao, setor, pessoa, cliente, so prioritarios, paradas), `query_agenda` (hoje, amanha, semana), `summary`, `create_task`, `assign`, `set_status`, `mark_priority`, `reschedule` (muda o dia ou a hora de um compromisso futuro, achado pelo titulo, caso ou cliente; mostra o antes e o depois e so o `1` aplica; o historico do caso guarda a remarcacao), `draft_message` (escreve o pedido a uma pessoa da equipe sobre uma demanda, por exemplo lancar as ferias; o texto e montado pelo codigo com titulo, resumo e proximo passo; o `1` do socio aprova e o agente devolve o texto para o proprio socio repassar, sem enviar a ninguem fora dos socios), `unknown`.
