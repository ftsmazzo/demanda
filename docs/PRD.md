# PRD — Demanda

> Product Requirements Document — o quê e por quê, não como.
> Fonte: [x] Entrevista com usuário  [ ] Leitura de código existente
> **Versão 0.2.** Recorte de MVP definido em 2026-10-24. O cliente piloto (Eliezer) ainda não respondeu às perguntas; a validação acontece pelo caso exemplo e pelo uso real do piloto, medindo e ajustando. Itens `[HIPÓTESE]` são medidos no piloto, não são pré-requisito.

**Data**: 2026-10-24
**Responsável**: Fábrica dos Dados (gestao@fabricadosdados.com.br)

## 1. Resumo em uma frase

Plataforma multi-tenant que "escuta" o WhatsApp oficial de uma empresa de serviços (começando por uma contabilidade), transforma as mensagens em tarefas, compromissos e pendências organizadas por setor, e mantém um agente de IA que fala só com os donos sobre o que está parado e o andamento do escritório.

## 2. Problema e contexto

- **Problema real:** muitas pessoas enviam mensagens ao WhatsApp do escritório e compromissos, tarefas, ações administrativas e pedidos internos (folgas, afastamentos) se perdem. Os donos não têm visão do que está parado, de quem é cada coisa nem do andamento geral.
- **Como é resolvido hoje:** leitura manual do WhatsApp pelos donos e equipe, memória das pessoas e controles soltos.
- **Por que agora:** o dono (Eliezer) relatou sofrimento para gerenciar, organizar, direcionar e monitorar o que chega. A Fábrica já tem o Prumo, com linha parecida e a escuta do WhatsApp via Evolution funcionando sem problemas.
- **Natureza do conteúdo:** conversas de rotina do escritório, em um número que todos sabem que é lido pelos donos. Não há tratamento de assuntos sigilosos. Os donos continuam lendo as mensagens, agora também dentro da aplicação, organizadas.

## 3. Público-alvo

- **Cliente do produto (tenant):** empresas de serviço com volume alto de demandas por WhatsApp. Piloto: a contabilidade do Eliezer. Depois, outras contabilidades e outros segmentos.
- **Persona principal:** sócio/dono. Quer visão, cobrança e resumo.
- **Perfis no MVP (3 papéis fixos):** Sócio (vê tudo), Gestor de setor (vê o seu setor), Colaborador (vê o que é seu).
- **Quem manda mensagem (não usa a plataforma):** clientes, fornecedores e colaboradores do escritório.

## 4. Objetivos e métricas de sucesso

Metas são `[HIPÓTESE]` e passam a ser medidas desde o primeiro dia de piloto.

| Objetivo | Métrica | Meta inicial |
|---|---|---|
| Nenhuma demanda sem dono | % de demandas com responsável em até 1 dia útil | ≥ 90% |
| Reduzir demandas paradas | Pendências sem movimento além do prazo | tendência de queda semana a semana |
| Visão dos donos | Resumo diário aberto/respondido pelos sócios | ≥ 70% dos dias úteis |
| Classificar bem | % de mensagens classificadas sem correção manual | ≥ 80% no início, subindo com o uso |
| Adoção | Equipe ativa na plataforma por semana | ≥ 70% |

Definições para medir:
- **Dono:** responsável atribuído por regra, pela IA ou por uma pessoa (registra-se a origem).
- **Classificada sem correção:** setor e tipo que ninguém alterou em até 2 dias úteis.
- **Resumo lido:** o sócio abriu o resumo no painel ou respondeu ao agente (não depende de confirmação de leitura do WhatsApp).

## 5. Escopo

### MVP (primeira entrega)
- Multi-tenant na base: `tenant_id` em todas as tabelas e isolamento por RLS. No início há um tenant em uso (piloto) e um de teste.
- Escuta do WhatsApp oficial do escritório via Evolution API (recebidas e enviadas), sem disparos por esse número.
- Classificação por regras + IA: setor, tipo, urgência e cliente.
- Fila de "não classificadas" e correção em um clique, que realimenta as regras.
- Contatos: cada número que interage fica registrado, com tipo (cliente, fornecedor, colaborador) e setores que o atendem.
- Quadros: Kanban de demandas, tarefas com barra de progresso e agenda de compromissos.
- Setores configuráveis (cadastro simples) e 3 papéis fixos.
- Agente dos donos: resumo diário, alerta de pendências paradas e alerta crítico.
- Painel executivo simples (abertas, atrasadas, por setor, carga por pessoa).
- Auditoria leve (quem alterou o quê) e controle de acesso por papel.

### Fase 2 (já preparada no modelo de dados)
- Painel de perfis com liga/desliga por tela e ação (o catálogo de permissões já existe no modelo; a fase 2 é a interface).
- Escopo de dados configurável por perfil.
- Resumo semanal do agente.
- Múltiplos canais por tenant e templates por segmento.
- Agente de IA que conduz a configuração (entrevista, o usuário aprova).
- Transcrição de áudio e leitura de imagens/documentos.

### Fora do escopo por enquanto
- Disparo de mensagens e resposta automática a clientes.
- Integração com sistema contábil/ERP.
- App mobile nativo (web responsivo).
- Cobrança dos tenants (billing).
- Motor de regras genérico e arbitrário.

## 6. Funcionalidades principais

| Funcionalidade | Prioridade | Descrição curta |
|---|---|---|
| Ingestão do WhatsApp | MVP | Webhook da Evolution, grava no banco com idempotência. |
| Classificação e roteamento | MVP | Regras + IA definem setor, tipo, urgência e cliente. |
| Correção em um clique | MVP | Humano corrige; vira regra/exemplo. |
| Contatos por setor | MVP | Número registrado, tipo e setores. |
| Kanban, tarefas, compromissos | MVP | Quadros com status, progresso e agenda. |
| Setores e 3 papéis fixos | MVP | Cadastro simples e acesso por papel. |
| Agente: resumo diário e alertas | MVP | Pelo WhatsApp, só aos sócios. |
| Painel executivo | MVP | Visão geral por setor e pessoa. |
| Auditoria leve | MVP | Registro de alterações. |
| Painel de perfis liga/desliga | Fase 2 | Interface sobre o catálogo de permissões. |
| Resumo semanal | Fase 2 | Mesmo motor do diário. |
| Agente de configuração | Fase 2 | Entrevista e proposta aprovada pelo usuário. |
| Áudio, imagem e documento | Fase 2 | Transcrição, visão e extração. |
| Templates por segmento | Fase 2 | Ponto de partida por tipo de empresa. |

## 7. Restrições de negócio

- **Prazo e orçamento:** sem definição. Estratégia: entregas curtas e piloto cedo.
- **Privacidade (proporcional ao contexto):** o número é público do escritório e os donos já leem tudo. No MVP: acesso por papel, auditoria leve, aviso interno de que as conversas são organizadas na plataforma, retenção configurável (padrão: manter) e minimização do que vai à IA (só o necessário). Contrato e política mais formais entram quando houver novos clientes.

## 8. Riscos e premissas

- **Premissa:** escutar sem enviar mantém o número seguro (experiência do Prumo). Mitigação: monitor da instância, alerta de queda, reconexão e reconciliação periódica.
- **Premissa:** os donos aceitam o agente por WhatsApp. Mitigação: o mesmo conteúdo fica no painel.
- **Risco (médio):** a classificação erra e o quadro vira ruído. Mitigação: fila de não classificadas, correção em um clique, medição desde o dia 1 e conjunto de mensagens rotuladas que cresce com o uso.
- **Risco (médio):** uma resposta curta ("ok", "pode ser") ser aprovação de tarefa. Mitigação: respostas curtas anexam-se à conversa e à tarefa aberta, nunca são descartadas.
- **Risco (médio):** ligar resposta à tarefa é frágil. Mitigação: ligar por conversa e contato, com revisão humana quando houver ambiguidade.
- **Risco (médio):** sócio em mais de um tenant no número do agente. Mitigação: o agente pergunta de qual empresa; a regra de resolução fica no TRD.
- **Risco (baixo/médio):** custo de IA. Mitigação: modelo leve para classificar, cache e limite por tenant.
- **Risco (alto):** escopo crescer antes de validar. Mitigação: este recorte; tudo da fase 2 só entra após uso real.

## 9. Decisões tomadas

| Decisão | Escolha | Data |
|---|---|---|
| Arquitetura | Multi-tenant desde o dia 1 (`tenant_id` + RLS) | 2026-10-24 |
| Cliente piloto | Eliezer (contabilidade) | 2026-10-24 |
| Escuta do WhatsApp | Evolution API, somente leitura | 2026-10-24 |
| Número do agente | Um número único da plataforma; tenant identificado pelo telefone do sócio | 2026-10-24 |
| Recorte de MVP | 3 papéis fixos, agente com resumo diário e alertas, painel de perfis na fase 2 | 2026-10-24 |
| Validação | Caso exemplo + piloto com medição, sem esperar respostas do cliente | 2026-10-24 |
| Privacidade | Proporcional: acesso por papel, auditoria leve, aviso interno | 2026-10-24 |

## 10. Perguntas que ficam para observar no piloto (não bloqueiam)

1. Qual a proporção real de clientes, fornecedores e colaboradores nas mensagens?
2. Os setores reais coincidem com o template do caso exemplo?
3. O resumo diário às 18:00 é o melhor horário?
4. Quais classificações mais recebem correção?
5. Quanto tempo as demandas ficam paradas hoje (linha de base do primeiro mês)?
