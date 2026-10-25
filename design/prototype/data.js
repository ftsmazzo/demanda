// Dados ficticios de uma contabilidade, so para o prototipo.
export const PEOPLE = [
  { id: "carlos", name: "Carlos Mendes", initials: "CM", role: "Sócio" },
  { id: "rafael", name: "Rafael Souza", initials: "RS", role: "Gestor fiscal" },
  { id: "juliana", name: "Juliana Prado", initials: "JP", role: "Gestora societário" },
  { id: "patricia", name: "Patrícia Alves", initials: "PA", role: "Gestora contábil" },
  { id: "marcos", name: "Marcos Teixeira", initials: "MT", role: "Gestor de DP" },
  { id: "bruno", name: "Bruno Costa", initials: "BC", role: "Colaborador fiscal" },
  { id: "aline", name: "Aline Ramos", initials: "AR", role: "RH interno" },
];

export const SECTORS = {
  fiscal: { name: "Fiscal", color: "var(--sector-fiscal)" },
  contabil: { name: "Contábil", color: "var(--sector-contabil)" },
  dp: { name: "Pessoal", color: "var(--sector-dp)" },
  societario: { name: "Societário", color: "var(--sector-societario)" },
  financeiro: { name: "Financeiro", color: "var(--sector-financeiro)" },
  triagem: { name: "Triagem", color: "var(--sector-triagem)" },
  "rh-interno": { name: "RH interno", color: "var(--sector-rh)" },
};

export const STATUSES = [
  { id: "novo", name: "Novas" },
  { id: "em_andamento", name: "Em andamento" },
  { id: "aguardando", name: "Aguardando" },
  { id: "concluido", name: "Concluídas" },
];

export const URGENCIES = { normal: "Normal", alta: "Alta", critica: "Crítica" };

const steps = (done, total, labels = []) =>
  Array.from({ length: total }, (_, i) => ({ t: labels[i] || `Etapa ${i + 1}`, done: i < done }));

export const DEMANDS = [
  {
    id: 1, title: "Já pedi 3 vezes a certidão negativa, ninguém me responde", who: "Clínica Vida",
    phone: "9106", sector: "societario", urgency: "critica", status: "novo", idle: 26,
    assignee: "juliana", steps: steps(0, 3, ["Localizar o pedido anterior", "Emitir a certidão", "Responder ao cliente"]),
    msgs: [
      { out: false, t: "Boa tarde. Preciso da certidão negativa da clínica.", at: "ter 09:12" },
      { out: false, t: "Alguém pode me responder? Já pedi duas vezes.", at: "ter 11:40" },
      { out: false, t: "Já pedi 3 vezes a certidão negativa, ninguém me responde!!", at: "ter 14:05" },
    ],
  },
  {
    id: 2, title: "Quando vence o DAS de outubro?", who: "Oficina do Zé", phone: "0103",
    sector: "fiscal", urgency: "normal", status: "novo", idle: 52, assignee: null, steps: [],
    msgs: [{ out: false, t: "Quando vence o DAS esse mês?", at: "ter 09:40" }],
  },
  {
    id: 3, title: "Notas fiscais de outubro para fechar o mês", who: "Padaria Pão Quente", phone: "0101",
    sector: "fiscal", urgency: "normal", status: "novo", idle: 4, assignee: "bruno",
    steps: steps(1, 4, ["Receber as 12 notas", "Conferir valores", "Lançar", "Confirmar com o cliente"]),
    msgs: [{ out: false, t: "Segue as notas fiscais pra fechar o mês", at: "ter 08:12" }],
  },
  {
    id: 4, title: "Boleto da internet vence dia 10", who: "NetFibra", phone: "0105", sector: "financeiro",
    urgency: "normal", status: "novo", idle: 2, assignee: null, steps: [],
    msgs: [{ out: false, t: "Segue boleto da internet, vence dia 10", at: "ter 11:30" }],
  },
  {
    id: 5, title: "Pedido de folga no dia 30", who: "Ana Paula", phone: "0104", sector: "rh-interno",
    urgency: "normal", status: "novo", idle: 6, assignee: "aline", restricted: true, steps: [],
    msgs: [{ out: false, t: "Preciso de folga dia 30, posso?", at: "ter 10:15" }],
  },
  {
    id: 6, title: "Abertura da filial do Mercado Bom Preço", who: "Mercado Bom Preço", phone: "0102",
    sector: "societario", urgency: "alta", status: "em_andamento", idle: 20, assignee: "juliana",
    steps: steps(2, 5, ["Contrato social", "Consulta de viabilidade", "Inscrição estadual", "Alvará", "CNPJ da filial"]),
    msgs: [
      { out: false, t: "Quinta às 15h dá pra falar sobre a abertura da filial?", at: "ter 09:03" },
      { out: true, t: "Dá sim. Já separei os documentos que preciso de vocês.", at: "ter 09:50" },
    ],
  },
  {
    id: 7, title: "Rescisão do funcionário João", who: "Autopeças Silva", phone: "0107", sector: "dp",
    urgency: "alta", status: "em_andamento", idle: 8, assignee: "marcos",
    steps: steps(3, 4, ["Dados do desligamento", "Cálculo", "Conferência", "Envio ao cliente"]), msgs: [],
  },
  {
    id: 8, title: "Balancete de setembro", who: "Grupo Alvorada", phone: "0108", sector: "contabil",
    urgency: "normal", status: "em_andamento", idle: 31, assignee: "patricia", steps: steps(5, 7), msgs: [],
  },
  {
    id: 9, title: "Guia do Simples de outubro", who: "Mercearia do Vale", phone: "0109", sector: "fiscal",
    urgency: "alta", status: "em_andamento", idle: 3, assignee: "rafael", steps: steps(1, 2), msgs: [],
  },
  {
    id: 10, title: "Reunião sobre a filial na quinta, às 15h", who: "Mercado Bom Preço", phone: "0102",
    sector: "societario", urgency: "normal", status: "aguardando", idle: 70, assignee: "juliana",
    steps: steps(0, 1, ["Confirmação do cliente"]), msgs: [],
  },
  {
    id: 11, title: "Conciliação bancária de outubro", who: "Grupo Alvorada", phone: "0108", sector: "contabil",
    urgency: "normal", status: "aguardando", idle: 98, assignee: "patricia",
    steps: steps(2, 6, ["Extrato recebido", "Importar", "Conferir", "Pendências", "Fechar", "Enviar"]), msgs: [],
  },
  {
    id: 12, title: "Cálculo do 13º salário", who: "Autopeças Silva", phone: "0107", sector: "dp",
    urgency: "normal", status: "aguardando", idle: 28, assignee: "marcos", steps: steps(1, 3), msgs: [],
  },
  { id: 13, title: "Alvará da loja renovado", who: "Calçados Lima", phone: "0110", sector: "societario",
    urgency: "normal", status: "concluido", idle: 0, closedAgo: 52, assignee: "juliana", steps: steps(3, 3), msgs: [] },
  { id: 14, title: "DAS de setembro emitido", who: "Oficina do Zé", phone: "0103", sector: "fiscal",
    urgency: "normal", status: "concluido", idle: 0, closedAgo: 120, assignee: "bruno", steps: steps(2, 2), msgs: [] },
  { id: 15, title: "Certidão negativa federal", who: "Padaria Pão Quente", phone: "0101", sector: "societario",
    urgency: "normal", status: "concluido", idle: 0, closedAgo: 190, assignee: "juliana", steps: steps(2, 2), msgs: [] },
];

export const CLOSED_TOTAL = 12;
