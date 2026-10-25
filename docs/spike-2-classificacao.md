# Spike 2: classificacao das mensagens

Objetivo: transformar cada mensagem recebida em setor, tipo, urgencia e cliente, medindo o acerto (TRD, secoes 6 e 12).

## Como funciona

1. **Regras primeiro** (`app/classification/rules.py`, versao `contabilidade-v1.2`): palavras e frases do dominio, sem custo. Quando acham setor e tipo, decidem sozinhas (confianca 0.9) e a IA nao e chamada.
2. **IA so no que sobra** (`llm.py`): Claude Haiku 5.5 (modelo trocavel por `CLASSIFIER_MODEL`), saida em JSON com schema fixo e validacao estrita. O texto da mensagem vai como dado delimitado: sem colchetes angulares, com CPF/CNPJ/numeros longos mascarados e limitado a 2000 caracteres. Mensagens anteriores da mesma conversa (ate 5) vao junto, tambem como dado.
3. **Fallback que nunca perde mensagem**: IA fora do ar, resposta invalida, erro inesperado, texto vazio ou confianca abaixo de 0.6 resultam em `source=fallback`, `needs_review=true`, setor triagem (ou o que as regras acharam).
4. **Ruido e respostas curtas**: agradecimentos, saudacoes e pontuacao viram `noise`. "ok", "pode ser" e "fechado" com demanda aberta viram `attach_reply` (nunca sao descartados).
5. Cada resultado fica em `message_classifications` (RLS por tenant, historico append-only, versao das regras e modelo registrados).

## Rodar

No console do servico `api`:

```bash
python -m app.cli classify-pending --no-llm      # so regras
python -m app.cli classify-pending               # regras + IA (exige ANTHROPIC_API_KEY)
python -m app.cli classify-pending --limit 50    # limite por tenant (1 a 1000)
```

Precisa de `APP_DATABASE_URL` (o login restrito). Rode uma execucao por vez.

Para ligar a IA: no EasyPanel, servico `api`, adicione a variavel `ANTHROPIC_API_KEY` e reimplante.

## Revisar o resultado

```bash
python -m app.cli review                  # ultimas 30 classificadas
python -m app.cli review --needs-review   # so as que pedem revisao humana
python -m app.cli review --limit 100      # ate 200
```

Cada linha: data, final do telefone, `setor/tipo/urgencia` (ou `noise`/`attach_reply`), origem (`rule`, `llm` ou `fallback`) e o inicio do texto.

## Medir

```bash
python -m app.classification.evaluation --errors         # so regras
python -m app.classification.evaluation --llm --errors   # com IA (chamadas reais, custo)
```

O conjunto rotulado (`app/classification/golden/contabilidade_v1.jsonl`, 60 mensagens sinteticas) foi escrito pela equipe e as regras foram ajustadas olhando para ele: os numeros dele sao otimistas. **A medida que vale e a das mensagens reais do piloto**: depois de rodar `classify-pending`, revise as linhas com `needs_review` e corrija os erros para virarem novos casos do conjunto.

Resultado atual so com regras no conjunto sintetico: cobertura 82%, precisao 100% quando decidem, 1 erro em 60.

## Limitacoes conhecidas

- O contexto ainda nao traz tipo do contato, demanda aberta nem setor padrao do canal (faltam as tabelas de contatos e demandas). Efeito: "ok" vira ruido em vez de anexar a uma demanda, e a regra de RH interno ainda nao dispara em producao.
- Nao ha tela de revisao nem correcao em um clique (proxima etapa); hoje a revisao e por consulta ao banco.
- Sem controle de custo por tenant alem do `--limit` e do teto de tamanho do texto.
- Sem protecao contra duas execucoes simultaneas (pagaria a IA duas vezes pela mesma mensagem).
