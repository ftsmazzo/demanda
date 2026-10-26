"""Dados ficticios para a demonstracao local (nada disto vai para producao)."""

import psycopg

from app.provisioning import create_channel, create_tenant, create_user

PASSWORD = "demo-senha-123"
TENANT_SLUG = "demo"

# (chave, nome, e-mail, papel, setores)
USERS = [
    ("carlos", "Carlos Mendes", "carlos@demo.com", "socio", ()),
    ("rafael", "Rafael Souza", "rafael@demo.com", "gestor", ("fiscal",)),
    ("juliana", "Juliana Prado", "juliana@demo.com", "gestor", ("societario",)),
    ("patricia", "Patrícia Alves", "patricia@demo.com", "gestor", ("contabil",)),
    ("marcos", "Marcos Teixeira", "marcos@demo.com", "gestor", ("dp",)),
    ("bruno", "Bruno Costa", "bruno@demo.com", "colaborador", ("fiscal",)),
    ("aline", "Aline Ramos", "aline@demo.com", "colaborador", ("rh-interno",)),
]

# (titulo, contato, final do telefone, setor, urgencia, status, horas paradas, responsavel, etapas)
DEMANDS = [
    (
        "Já pedi 3 vezes a certidão negativa, ninguém me responde",
        "Clínica Vida",
        "9106",
        "societario",
        "critica",
        "novo",
        26,
        "juliana",
        [
            ("Localizar o pedido anterior", False),
            ("Emitir a certidão", False),
            ("Responder ao cliente", False),
        ],
    ),
    (
        "Quando vence o DAS de outubro?",
        "Oficina do Zé",
        "0103",
        "fiscal",
        "normal",
        "novo",
        52,
        None,
        [],
    ),
    (
        "Notas fiscais de outubro para fechar o mês",
        "Padaria Pão Quente",
        "0101",
        "fiscal",
        "normal",
        "novo",
        4,
        "bruno",
        [
            ("Receber as 12 notas", True),
            ("Conferir valores", False),
            ("Lançar", False),
            ("Confirmar com o cliente", False),
        ],
    ),
    (
        "Boleto da internet vence dia 10",
        "NetFibra",
        "0105",
        "financeiro",
        "normal",
        "novo",
        2,
        None,
        [],
    ),
    (
        "Pedido de folga no dia 30",
        "Ana Paula",
        "0104",
        "rh-interno",
        "normal",
        "novo",
        6,
        "aline",
        [],
    ),
    (
        "Abertura da filial do Mercado Bom Preço",
        "Mercado Bom Preço",
        "0102",
        "societario",
        "alta",
        "em_andamento",
        20,
        "juliana",
        [
            ("Contrato social", True),
            ("Consulta de viabilidade", True),
            ("Inscrição estadual", False),
            ("Alvará", False),
            ("CNPJ da filial", False),
        ],
    ),
    (
        "Rescisão do funcionário João",
        "Autopeças Silva",
        "0107",
        "dp",
        "alta",
        "em_andamento",
        8,
        "marcos",
        [
            ("Dados do desligamento", True),
            ("Cálculo", True),
            ("Conferência", True),
            ("Envio ao cliente", False),
        ],
    ),
    (
        "Balancete de setembro",
        "Grupo Alvorada",
        "0108",
        "contabil",
        "normal",
        "em_andamento",
        31,
        "patricia",
        [
            ("Extrato", True),
            ("Lançamentos", True),
            ("Conciliação", True),
            ("Revisão", True),
            ("Assinatura", True),
            ("Envio", False),
            ("Arquivo", False),
        ],
    ),
    (
        "Guia do Simples de outubro",
        "Mercearia do Vale",
        "0109",
        "fiscal",
        "alta",
        "em_andamento",
        3,
        "rafael",
        [("Apurar", True), ("Emitir a guia", False)],
    ),
    (
        "Reunião sobre a filial na quinta, às 15h",
        "Mercado Bom Preço",
        "0102",
        "societario",
        "normal",
        "aguardando",
        70,
        "juliana",
        [("Confirmação do cliente", False)],
    ),
    (
        "Conciliação bancária de outubro",
        "Grupo Alvorada",
        "0108",
        "contabil",
        "normal",
        "aguardando",
        98,
        "patricia",
        [
            ("Extrato recebido", True),
            ("Importar", True),
            ("Conferir", False),
            ("Pendências", False),
            ("Fechar", False),
            ("Enviar", False),
        ],
    ),
    (
        "Cálculo do 13º salário",
        "Autopeças Silva",
        "0107",
        "dp",
        "normal",
        "aguardando",
        28,
        "marcos",
        [("Folha base", True), ("Médias", False), ("Conferência", False)],
    ),
    (
        "Alvará da loja renovado",
        "Calçados Lima",
        "0110",
        "societario",
        "normal",
        "concluido",
        0,
        "juliana",
        [("Protocolo", True), ("Retirada", True), ("Entrega", True)],
    ),
    (
        "DAS de setembro emitido",
        "Oficina do Zé",
        "0103",
        "fiscal",
        "normal",
        "concluido",
        0,
        "bruno",
        [("Apurar", True), ("Emitir", True)],
    ),
]

CONVERSATIONS = {
    "Já pedi 3 vezes a certidão negativa, ninguém me responde": [
        ("in", "Boa tarde. Preciso da certidão negativa da clínica.", 26 * 60 + 300),
        ("in", "Alguém pode me responder? Já pedi duas vezes.", 26 * 60 + 100),
        ("in", "Já pedi 3 vezes a certidão negativa, ninguém me responde!!", 26 * 60),
    ],
    "Abertura da filial do Mercado Bom Preço": [
        ("in", "Quinta às 15h dá pra falar sobre a abertura da filial?", 20 * 60 + 70),
        ("out", "Dá sim. Já separei os documentos que preciso de vocês.", 20 * 60),
    ],
}


def seed(conn: psycopg.Connection) -> dict[str, str]:
    tenant = create_tenant(conn, slug=TENANT_SLUG, name="Contabilidade Demo")
    channel, _ = create_channel(conn, tenant_id=tenant, name="WhatsApp", instance_name="demo")
    ids = {}
    for key, name, email, role, sectors in USERS:
        ids[key] = create_user(
            conn,
            tenant_id=tenant,
            email=email,
            name=name,
            role=role,
            password=PASSWORD,
            sectors=sectors,
        )

    contacts: dict[str, object] = {}
    for index, (title, who, tail, sector, urgency, status, idle, owner, steps) in enumerate(
        DEMANDS
    ):
        if who not in contacts:
            contacts[who] = conn.execute(
                "INSERT INTO contacts (tenant_id, phone, name, kind) VALUES (%s, %s, %s, 'cliente') RETURNING id",
                (tenant, f"55119999{tail}", who),
            ).fetchone()[0]
        closed = "now() - interval '2 days'" if status == "concluido" else "NULL"
        demand = conn.execute(
            "INSERT INTO demands (tenant_id, contact_id, sector, kind, urgency, status, title, assignee_id, "
            f"last_activity_at, closed_at) VALUES (%s, %s, %s, 'tarefa', %s, %s, %s, %s, now() - make_interval(hours => %s), {closed}) RETURNING id",
            (tenant, contacts[who], sector, urgency, status, title, ids.get(owner), idle),
        ).fetchone()[0]
        for label, done in steps:
            conn.execute(
                "INSERT INTO subtasks (tenant_id, demand_id, title, done) VALUES (%s, %s, %s, %s)",
                (tenant, demand, label, done),
            )
        for number, (direction, text, minutes_ago) in enumerate(
            CONVERSATIONS.get(title, [("in", title, idle * 60 + 5)])
        ):
            message = conn.execute(
                "INSERT INTO messages (tenant_id, channel_id, provider_message_id, direction, remote_jid, contact_phone, "
                "message_type, text, provider_timestamp, raw, contact_id) VALUES (%s, %s, %s, %s, %s, %s, 'conversation', %s, "
                "now() - make_interval(mins => %s), '{}'::jsonb, %s) RETURNING id",
                (
                    tenant,
                    channel,
                    f"demo-{index}-{number}",
                    direction,
                    f"55119999{tail}@s.whatsapp.net",
                    f"55119999{tail}",
                    text,
                    minutes_ago,
                    contacts[who],
                ),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)",
                (tenant, demand, message),
            )
    _seed_cases(conn, tenant)
    return {"tenant": TENANT_SLUG, "password": PASSWORD}


def _seed_cases(conn: psycopg.Connection, tenant) -> None:
    """Resumo, proximo passo, historico, compromisso e um caso a revisar (como a IA deixaria)."""
    rows = conn.execute(
        "SELECT id, title, contact_id FROM demands WHERE tenant_id = %s ORDER BY created_at LIMIT 4",
        (tenant,),
    ).fetchall()
    notes = [
        (
            "O cliente pediu a guia do DAS de outubro e quer receber ainda hoje.",
            "Emitir a guia e enviar pelo WhatsApp.",
        ),
        (
            "Reuniao para definir o projeto IE, ainda sem confirmacao de todos.",
            "Confirmar o horario com a Poli.",
        ),
        ("A funcionaria Ana pediu ferias para dezembro.", "Lancar as ferias no sistema de RH."),
        (
            "Balancete de setembro em conferencia, faltam dois extratos.",
            "Cobrar os extratos do cliente.",
        ),
    ]
    for (demand, _title, _contact), (summary, step) in zip(rows, notes, strict=False):
        conn.execute(
            "UPDATE demands SET summary = %s, next_step = %s, ai_updated_at = now() WHERE id = %s",
            (summary, step, demand),
        )
        conn.execute(
            "INSERT INTO case_events (tenant_id, demand_id, actor, kind) VALUES (%s, %s, 'ai', 'created')",
            (tenant, demand),
        )
        conn.execute(
            "INSERT INTO case_events (tenant_id, demand_id, actor, kind) VALUES (%s, %s, 'ai', 'attached')",
            (tenant, demand),
        )
    if len(rows) >= 2:
        demand, _, contact = rows[1]
        conn.execute(
            "INSERT INTO appointments (tenant_id, demand_id, contact_id, title, starts_at, status) "
            "VALUES (%s, %s, %s, 'Reuniao do projeto IE', now() + interval '2 days', 'proposed')",
            (tenant, demand, contact),
        )
        conn.execute(
            "INSERT INTO appointments (tenant_id, demand_id, contact_id, title, starts_at, status) "
            "VALUES (%s, %s, %s, 'Alinhamento do balancete', "
            "date_trunc('day', now()) + interval '1 day 14 hours', 'confirmed'), "
            "(%s, %s, %s, 'Ligacao sobre o DAS', "
            "date_trunc('day', now()) + interval '2 days 14 hours 30 minutes', 'confirmed'), "
            "(%s, %s, %s, 'Visita ao cliente', "
            "date_trunc('day', now()) + interval '4 days 9 hours', 'proposed')",
            (tenant, demand, contact, tenant, demand, contact, tenant, demand, contact),
        )
        conn.execute(
            "UPDATE demands SET needs_review = true, review_reason = 'confirmar agrupamento' WHERE id = %s",
            (rows[3][0],),
        )
        conn.execute(
            "INSERT INTO case_events (tenant_id, demand_id, actor, kind, data) "
            "VALUES (%s, %s, 'ai', 'review', %s)",
            (tenant, rows[3][0], '{"reason": "confirmar agrupamento", "candidate": null}'),
        )
