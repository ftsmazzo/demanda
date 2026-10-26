# Etapa 1: conversas e casos com IA

Decisoes da sessao de desenho (PM, arquitetura, desenvolvimento e QA) de 2026-10-26.

## Problema

Hoje a unidade e a mensagem: cada frase vira card ou compromisso, o titulo e o texto cru da primeira mensagem, e o sistema rotula o setor mas nao faz nada com o assunto (ex.: "funcionario pediu ferias" so recebeu um setor). Nao ha leitura da conversa inteira.

## Modelo

- O **caso** e a propria `demands` (estendida): `summary`, `next_step`, `needs_review`, `review_reason`, `ai_updated_at`; novo tipo `nota`.
- `case_events` e o historico de cada caso: quem mudou (`ai`, `rules`, `user`), o que mudou e a mensagem de origem. Nada apaga mensagem bruta.
- Compromisso continua em `appointments`, ligado ao caso. Remarcacao atualiza o compromisso existente (o antes e o depois ficam no historico).

## Fluxo

1. A classificacao por mensagem continua como primeiro filtro (ruido, eco do agente, resposta curta).
2. Para o que sobra, **uma chamada de IA por mensagem**, fora de qualquer trava, recebendo so: a mensagem, o tipo do contato, os casos abertos do contato (titulo, resumo, tipo, ultimas mensagens) e a data/dia da semana locais. Sem CPF/CNPJ.
3. A IA devolve JSON validado: `attach` (a um caso), `new` (caso novo) ou `ignore`, com titulo, resumo, tipo, setor, urgencia, proximo passo, confianca e, se houver, a **frase** do compromisso ("quinta as 10"). **A conta de data e fuso e feita pelo codigo**, nunca pela IA.
4. Sob a trava do contato o codigo revalida (o caso ainda existe, e aberto e e do mesmo contato) e aplica. Falha, timeout, JSON invalido ou teto de custo: volta ao comportamento atual por regras.

## Regras de seguranca

- Confianca baixa nunca altera nada existente: cria caso **separado**, marcado `needs_review` ("confirmar agrupamento"), com um toque para juntar. Juntar errado esconde pedido de cliente; separar errado so cria um card a mais.
- Remarcacao com confianca baixa vira **proposta** no historico, nao muda o compromisso.
- Toda mudanca da IA entra em `case_events` e pode ser desfeita.
- Texto da mensagem e dado, nunca instrucao (a IA nao escolhe acoes livres: so os tipos fixos).
- Teto diario de chamadas por tenant (`CASE_LLM_DAILY_CAP`).

## Aceite

O caso das ferias: "funcionario X pediu ferias", vindo de contato do escritorio, vira nota/tarefa em `rh-interno`, com responsavel sugerido e proximo passo. O rascunho de mensagem a quem lanca so sai com aprovacao do socio (etapa seguinte desta frente).
