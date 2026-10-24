# Simulação — Tenant de teste "Contabilidade Exemplo"

> Caso fictício completo para validar o PRD, o modelo de configuração e o comportamento do agente.
> Todos os nomes, telefones e valores são sintéticos. Telefones no padrão `55119999900xx`.
> Serve também de base para o seed de testes e para o template "Contabilidade v1".
>
> **Nota sobre o MVP (PRD v0.2):** no MVP existem 3 papéis fixos (Sócio, Gestor de setor, Colaborador). A matriz completa de perfis da seção 5, o escopo configurável, os múltiplos canais e o resumo semanal são **fase 2**, mas o modelo de dados já nasce preparado para eles. O caso continua valendo como alvo e como conjunto de testes.

## 1. Perfil da empresa (tenant)

| Campo | Valor |
|---|---|
| Nome | Contabilidade Exemplo Ltda |
| Slug | `contabilidade-exemplo` |
| Segmento / template | Contabilidade (`contabilidade-v1`) |
| Porte | 14 pessoas, ~180 clientes ativos |
| Fuso | America/Sao_Paulo |
| Horário comercial | Seg a sex, 08:00 às 18:00 |
| Dor declarada | Muitas pessoas mandam mensagem ao mesmo WhatsApp; compromissos, tarefas, ações administrativas e RH se perdem; os sócios não têm visão |

## 2. Jornada de criação (passo a passo)

Simula o que o administrador do tenant faz ao entrar pela primeira vez.

| Passo | Ação | Resultado |
|---|---|---|
| 1 | Plataforma cria o tenant e o primeiro usuário (sócio-administrador) | Tenant ativo em modo configuração |
| 2 | Escolhe o template "Contabilidade" | Setores, perfis e regras sugeridos são carregados como rascunho |
| 3 | Revisa os setores (renomeia, remove, cria) | 7 setores confirmados (seção 3) |
| 4 | Conecta a origem de mensagens: lê o QR code da instância Evolution do WhatsApp do escritório | Canal `ativo`, escutando |
| 5 | Ajusta a matriz de perfis (liga/desliga por tela e ação) | 6 perfis confirmados (seção 5) |
| 6 | Cadastra usuários e liga cada um a perfil e setor | 9 usuários (seção 6) |
| 7 | Cadastra o telefone dos sócios e ativa o agente: cada sócio manda um código de pareamento ao número da plataforma | Telefone do sócio vinculado ao tenant |
| 8 | Importa/classifica os números que já interagem (histórico recente do WhatsApp) | Contatos como cliente, fornecedor, colaborador ou desconhecido |
| 9 | Revisa as regras de roteamento e as regras do agente | Regras confirmadas (seções 7 e 8) |
| 10 | Rodada de teste: mensagens de exemplo caem nos setores certos | Tenant sai do modo configuração e passa a produção |

> Na fase 2, um agente de IA conduz os passos 2 a 9 em formato de entrevista e propõe tudo, e o usuário aprova no painel.

## 3. Setores

| Setor | Código | Gestor | Exemplos de demanda |
|---|---|---|---|
| Triagem / Atendimento | `triagem` | Fernanda | Mensagem sem setor claro, dúvida geral |
| Fiscal | `fiscal` | Rafael | Notas fiscais, impostos, DAS, obrigações |
| Contábil | `contabil` | Patrícia | Balancete, conciliação, fechamento mensal |
| Departamento Pessoal | `dp` | Marcos | Folha, admissão, rescisão, férias, atestado |
| Societário / Legalização | `societario` | Juliana | Abertura, alteração contratual, certidões, alvarás |
| Financeiro / Cobrança | `financeiro` | Carlos (sócio) | Honorários, boletos de fornecedor, inadimplência |
| Administrativo / RH interno | `rh-interno` | Carlos (sócio) | Folgas, contratação, advertência, benefícios da equipe |

`rh-interno` tem **visibilidade restrita**: só vê quem tiver a permissão específica.

## 4. Origens de mensagem (canais)

| Canal | Tipo | Número (sintético) | Setor padrão | Função |
|---|---|---|---|---|
| WhatsApp principal do escritório | Evolution (somente escuta) | 5511999990001 | `triagem` | Entrada geral dos clientes |
| WhatsApp do DP | Evolution (somente escuta) | 5511999990002 | `dp` | Folha e demandas de funcionários dos clientes |
| Número do agente | Plataforma (envio) | 5511999990000 | n/a | Fala só com os sócios |

Regras do canal:
- Mensagens recebidas **e enviadas** pelo escritório são captadas. A resposta de um colaborador indica que a demanda foi atendida.
- Nenhum disparo sai pelos números escutados.
- O número do agente é único da plataforma e atende todos os tenants. O tenant é resolvido pelo telefone do remetente, cadastrado como sócio no tenant.

## 5. Perfis e matriz de permissões

Cada célula é um toggle liga/desliga. O escopo de dados é separado: `tudo`, `meu setor` ou `minhas`.

| Tela / ação | Sócio | Gestor de setor | Colaborador | Triagem | RH interno | Somente leitura |
|---|---|---|---|---|---|---|
| Painel executivo | ligado | desligado | desligado | desligado | desligado | ligado |
| Caixa de entrada (mensagens) | ligado | ligado | ligado (só atribuídas) | ligado | desligado | desligado |
| Reclassificar mensagem | ligado | ligado | desligado | ligado | desligado | desligado |
| Kanban de demandas | ligado | ligado | ligado | ligado | desligado | ligado |
| Tarefas (criar/editar) | ligado | ligado | ligado | ligado | desligado | desligado |
| Compromissos / agenda | ligado | ligado | ligado | ligado | desligado | ligado |
| Pendências paradas | ligado | ligado | desligado | desligado | desligado | ligado |
| Resumos do agente (histórico) | ligado | desligado | desligado | desligado | desligado | ligado |
| Contatos / clientes | ligado | ligado | ligado | ligado | desligado | ligado |
| RH interno (demandas sensíveis) | ligado | desligado | desligado | desligado | ligado | desligado |
| Configurações: setores | ligado | desligado | desligado | desligado | desligado | desligado |
| Configurações: perfis e usuários | ligado | desligado | desligado | desligado | desligado | desligado |
| Configurações: canais e regras | ligado | desligado | desligado | desligado | desligado | desligado |
| Auditoria (quem viu/fez o quê) | ligado | desligado | desligado | desligado | desligado | desligado |

| Escopo de dados | Sócio | Gestor | Colaborador | Triagem | RH interno | Somente leitura |
|---|---|---|---|---|---|---|
| Padrão | tudo | meu setor | minhas | tudo (exceto RH interno) | `rh-interno` | tudo (exceto RH interno) |

## 6. Usuários

| Usuário | Perfil | Setor | Telefone (sintético) | Recebe do agente |
|---|---|---|---|---|
| Carlos Mendes | Sócio | financeiro, rh-interno | 5511999990011 | Sim |
| Helena Mendes | Sócio | todos | 5511999990012 | Sim |
| Fernanda Lopes | Gestor de setor | triagem | 5511999990013 | Não |
| Rafael Souza | Gestor de setor | fiscal | 5511999990014 | Não |
| Patrícia Alves | Gestor de setor | contabil | 5511999990015 | Não |
| Marcos Teixeira | Gestor de setor | dp | 5511999990016 | Não |
| Juliana Prado | Gestor de setor | societario | 5511999990017 | Não |
| Bruno Costa | Colaborador | fiscal | 5511999990018 | Não |
| Aline Ramos | RH interno | rh-interno | 5511999990019 | Não |

## 7. Regras de roteamento (ordem de avaliação)

| # | Condição | Ação |
|---|---|---|
| 1 | Remetente é colaborador do escritório e o assunto é folga, atestado, benefício, contratação | Setor `rh-interno`, visibilidade restrita |
| 2 | Canal = WhatsApp do DP | Setor padrão `dp` |
| 3 | Contato já vinculado a um setor e a mensagem é da mesma natureza | Mesmo setor do último atendimento |
| 4 | Palavras: DAS, nota, NF, imposto, ISS, ICMS, guia | `fiscal` |
| 5 | Palavras: folha, férias, rescisão, admissão, holerite, atestado | `dp` |
| 6 | Palavras: abertura, alteração contratual, CNPJ, alvará, certidão, filial | `societario` |
| 7 | Palavras: balancete, conciliação, DRE, fechamento, balanço | `contabil` |
| 8 | Palavras: boleto, honorário, cobrança, pagamento, fornecedor | `financeiro` |
| 9 | Nada acima | A IA classifica; confiança baixa vai para `triagem` |
| 10 | Agradecimento, bom dia, figurinha sem demanda aberta no contato | Arquivar como ruído (continua pesquisável) |
| 11 | Resposta curta ("ok", "pode ser", "fechado") em contato com demanda aberta | Anexar à conversa e à tarefa aberta, nunca descartar (pode ser aprovação) |

A IA também define **tipo** (tarefa, compromisso, dúvida, documento, cobrança, reclamação), **urgência** (normal, alta, crítica) e **cliente** (pelo número ou pelo nome citado).

## 8. Regras do agente (conversa só com os sócios)

| Regra | Valor |
|---|---|
| Pendência parada | Sem movimento por 1 dia útil (normal), 4 horas úteis (alta) |
| Alerta crítico | Imediato, qualquer hora comercial |
| Alertas de parada consolidados | 1 mensagem por dia às 09:00 |
| Resumo diário | Dias úteis às 18:00 |
| Resumo semanal | Segunda-feira às 08:00 |
| Silêncio | Sem mensagens fora de 07:00 às 20:00, exceto crítico |
| Conteúdo sensível (RH interno) | Só aparece para sócio com acesso a `rh-interno` |
| Interação do sócio | Pode perguntar ("o que está parado no fiscal?") e pedir cobrança ao responsável |

## 9. Caso real: um dia de mensagens (terça, 2026-10-20)

### 9.1 Entrada

| Hora | De | Mensagem | Classificação | Resultado |
|---|---|---|---|---|
| 08:12 | Cliente Padaria Pão Quente (5511999990101) | Foto de 12 notas fiscais + "pra fechar o mês" | `fiscal`, tarefa, normal | Tarefa "Lançar notas de outubro" ligada ao cliente, atribuída ao Bruno, prazo dia 25 |
| 09:03 | Cliente Mercado Bom Preço (5511999990102) | "Quinta às 15h dá pra falar sobre a abertura da filial?" | `societario`, compromisso, normal | Compromisso criado quinta 15:00, participantes Juliana + cliente, **aguardando confirmação** |
| 09:40 | Cliente Oficina do Zé (5511999990103) | "Quando vence o DAS esse mês?" | `fiscal`, dúvida, normal | Dúvida na fila do Rafael; resposta esperada em 1 dia útil |
| 10:15 | Colaboradora Ana Paula (5511999990104) | "Preciso de folga dia 30, posso?" | `rh-interno`, tarefa, normal | Demanda **restrita**, visível só à Aline e aos sócios com acesso |
| 11:30 | Fornecedor NetFibra (5511999990105) | "Segue boleto da internet, vence dia 10" | `financeiro`, cobrança, normal | Tarefa "Pagar boleto NetFibra", prazo dia 10 |
| 14:05 | Cliente Clínica Vida (5511999990106) | "Já pedi 3 vezes a certidão negativa, ninguém me responde!!" | `societario`, reclamação, **crítica** | Escalada à gestora Juliana e **alerta imediato aos sócios** |
| 14:20 | Várias pessoas | "Obrigado!", "ok", "bom dia" | ruído | Arquivadas, fora do quadro |

### 9.2 Alerta imediato (14:06)

Agente, pelo número da plataforma, para Carlos e Helena:

> Alerta crítico: a Clínica Vida reclamou que pediu a certidão negativa 3 vezes sem resposta (Societário, gestora Juliana). Última mensagem às 14:05. Quer que eu cobre a Juliana agora?

Carlos responde "cobra". O agente avisa a Juliana pelo painel e registra a cobrança na demanda.

### 9.3 Dia seguinte (quarta, 2026-10-21)

09:00, alerta consolidado de paradas aos sócios:

> Bom dia. Pendências sem movimento:
> 1. Dúvida do DAS da Oficina do Zé (Fiscal, Rafael): sem resposta há 1 dia útil.
> 2. Compromisso de quinta com o Mercado Bom Preço (Societário): cliente ainda não confirmou.
> Os demais itens estão em andamento.

### 9.4 Resumo diário (quarta, 18:00)

> Resumo de hoje, Contabilidade Exemplo
>
> Entraram 31 mensagens, 9 viraram demanda, 22 eram ruído ou já respondidas.
> Concluídas: 4. Em andamento: 11. Atrasadas: 2.
> Por setor: Fiscal 5 abertas (1 atrasada), Societário 3 (1 crítica tratada), DP 2, Contábil 1, Financeiro 2.
> Maior carga: Bruno (Fiscal) com 6 tarefas.
> Compromissos de amanhã: reunião com Mercado Bom Preço às 15:00.
> Precisa de você: dúvida do DAS sem resposta há 2 dias.

### 9.5 Resumo semanal (segunda, 08:00)

Mesmo formato, com: demandas abertas versus fechadas na semana, tempo médio até a primeira resposta por setor, clientes com mais reclamações, pendências mais antigas e carga por pessoa. Itens de `rh-interno` aparecem só para sócios com acesso.

## 10. Isolamento: o que este caso testa

| Cenário | Esperado |
|---|---|
| Aline (RH interno) abre o Kanban | Não vê tarefas de cliente nem de outros setores |
| Bruno (colaborador fiscal) abre a caixa de entrada | Vê só mensagens atribuídas a ele |
| Rafael (gestor fiscal) tenta abrir uma demanda do DP | Negado e registrado na auditoria |
| Helena (sócio) pergunta ao agente sobre RH interno | Responde, pois tem acesso ao setor |
| Telefone desconhecido escreve para o número do agente | Ignora ou pede código de pareamento; nunca revela dados |
| Segundo tenant de teste com telefone de sócio diferente | Nenhum dado cruza entre tenants |
| Mesmo telefone de sócio em dois tenants | O agente pergunta de qual empresa se trata antes de responder |

## 11. Decisões que a simulação deixa para o TRD

1. Número do agente: Evolution (flexível, mas envio proativo é risco de bloqueio) ou API oficial da Meta (estável, exige templates aprovados para mensagens fora da janela de 24 horas). Minha inclinação: oficial para o agente, Evolution só para escuta.
2. Como o agente lida com o telefone de sócio repetido em mais de um tenant.
3. Retenção e anonimização de mensagens (LGPD).
4. Transcrição de áudio no MVP ou depois.
