"""CLI administrativa: python -m app.cli <comando>. Usa DATABASE_URL (papel dono do schema)."""

import argparse
import getpass
import os
import re
import secrets
import sys

import psycopg

from app.classification.factory import build_classifier
from app.classification.store import classify_pending
from app.core.appointments import backfill_appointments
from app.core.demands import materialize_demands
from app.db import Database
from app.evolution_client import EvolutionClient, EvolutionError
from app.provisioning import create_channel, create_runtime_role, create_tenant, create_user
from app.security.tokens import ROLES

MAX_CLASSIFY_LIMIT = 1000


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    tenant = sub.add_parser("create-tenant", help="cria um tenant")
    tenant.add_argument("--slug", required=True)
    tenant.add_argument("--name", required=True)

    sub.add_parser(
        "create-runtime-role",
        help="cria o login de runtime; a senha vem da variavel APP_DB_PASSWORD",
    )

    classify = sub.add_parser(
        "classify-pending", help="classifica mensagens ainda sem classificacao"
    )
    classify.add_argument(
        "--limit", type=_bounded_limit, default=200, help="maximo por tenant (1 a 1000)"
    )
    classify.add_argument("--no-llm", action="store_true", help="so regras, sem chamar a IA")

    review = sub.add_parser("review", help="lista as ultimas mensagens classificadas")
    review.add_argument("--limit", type=_review_limit, default=30, help="quantidade (1 a 200)")
    review.add_argument(
        "--needs-review", action="store_true", help="so as que pedem revisao humana"
    )

    user = sub.add_parser("create-user", help="cria um usuario; a senha vem de USER_PASSWORD")
    user.add_argument("--tenant-slug", required=True)
    user.add_argument("--email", required=True)
    user.add_argument("--name", required=True)
    user.add_argument("--role", required=True, choices=ROLES)
    user.add_argument("--sector", action="append", default=[], help="repita para varios setores")

    demands = sub.add_parser("demands", help="lista as demandas (quadro em texto)")
    demands.add_argument("--limit", type=_review_limit, default=30, help="quantidade (1 a 200)")
    demands.add_argument("--open", action="store_true", help="so as nao concluidas")
    demands.add_argument("--tenant-slug", help="so as demandas deste tenant")

    sub.add_parser(
        "backfill-appointments",
        help="propoe compromissos para reunioes que ja viraram demanda",
    )

    add = sub.add_parser("add-recipient", help="cadastra um socio para receber os avisos do agente")
    add.add_argument("--tenant-slug", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--phone", required=True, help="com DDI e DDD, ex.: 5511999990101")
    add.add_argument("--user-email", help="e-mail do usuario socio ligado a este telefone")

    remove = sub.add_parser("remove-recipient", help="desativa um destinatario do agente")
    remove.add_argument("--tenant-slug", required=True)
    remove.add_argument("--phone", required=True)

    listing = sub.add_parser("recipients", help="lista quem recebe os avisos do agente")
    listing.add_argument("--tenant-slug", required=True)

    outbox = sub.add_parser("agent-outbox", help="ultimos avisos do agente e o estado de cada um")
    outbox.add_argument("--tenant-slug")
    outbox.add_argument("--limit", type=_review_limit, default=15, help="quantidade (1 a 200)")

    sub.add_parser(
        "setup-agent-webhook",
        help="configura na Evolution o webhook da instancia do agente (segredo e cabecalho)",
    )

    sub.add_parser("stats", help="contagem de mensagens e latencia por canal (medicao do spike)")

    channel = sub.add_parser("create-channel", help="cria um canal e mostra o segredo uma vez")
    channel.add_argument("--tenant-slug", required=True)
    channel.add_argument("--name", required=True)
    channel.add_argument("--instance", required=True, help="nome da instancia na Evolution")
    channel.add_argument("--listen-groups", action="store_true")
    return parser


_STATS_SQL = """
    SELECT c.id, c.name,
           count(m.id),
           count(m.id) FILTER (WHERE m.direction = 'in'),
           count(m.id) FILTER (WHERE m.direction = 'out'),
           max(m.received_at),
           avg(extract(epoch FROM m.received_at - m.provider_timestamp)),
           percentile_cont(0.95) WITHIN GROUP (
               ORDER BY extract(epoch FROM m.received_at - m.provider_timestamp))
    FROM channels c LEFT JOIN messages m ON m.channel_id = c.id
    GROUP BY c.id, c.name ORDER BY c.name
"""


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def _print_stats(conn: psycopg.Connection) -> int:
    for cid, name, total, inbound, outbound, last, avg_lat, p95 in conn.execute(_STATS_SQL):
        print(
            f"{cid} {name}: total={total} in={inbound} out={outbound} "
            f"ultima={last} latencia_media_s={_fmt(avg_lat)} latencia_p95_s={_fmt(p95)}"
        )
    return 0


_REVIEW_SQL = """
    SELECT m.provider_timestamp, m.contact_phone, m.text, c.sector, c.kind, c.urgency,
           c.source, c.needs_review, c.reason, c.action
    FROM (
        SELECT DISTINCT ON (message_id) *
        FROM message_classifications
        ORDER BY message_id, created_at DESC, id DESC
    ) c JOIN messages m ON m.id = c.message_id
    WHERE (NOT %s OR c.needs_review)
    ORDER BY m.provider_timestamp DESC
    LIMIT %s
"""
_REVIEW_TEXT_CHARS = 90


_DEMANDS_SQL = """
    SELECT d.status, d.sector, d.urgency, d.kind, d.title, c.name, c.phone,
           FLOOR(EXTRACT(EPOCH FROM (now() - d.last_activity_at)) / 3600)::int
    FROM demands d LEFT JOIN contacts c ON c.id = d.contact_id
    WHERE (NOT %s OR d.status <> 'concluido')
      AND (%s::uuid IS NULL OR d.tenant_id = %s::uuid)
    ORDER BY CASE d.status WHEN 'novo' THEN 1 WHEN 'em_andamento' THEN 2
                           WHEN 'aguardando' THEN 3 ELSE 4 END,
             CASE d.urgency WHEN 'critica' THEN 3 WHEN 'alta' THEN 2 ELSE 1 END DESC,
             d.last_activity_at DESC
    LIMIT %s
"""


def _print_demands(
    conn: psycopg.Connection, limit: int, *, only_open: bool, tenant_slug: str | None
) -> int:
    tenant_id = None
    if tenant_slug:
        found = conn.execute("SELECT id FROM tenants WHERE slug = %s", (tenant_slug,)).fetchone()
        if found is None:
            print(f"tenant nao encontrado: {tenant_slug}", file=sys.stderr)
            return 1
        tenant_id = found[0]
    rows = conn.execute(_DEMANDS_SQL, (only_open, tenant_id, tenant_id, limit)).fetchall()
    for status, sector, urgency, kind, title, name, phone, idle in rows:
        who = name or "sem nome"
        waiting = f"parada {idle}h" if status != "concluido" else "concluida"
        tail = phone[-4:] if phone else ""
        head = f"[{status}] {sector}/{urgency} {kind}"
        print(f"{head} | {who} ...{tail} | {waiting} | {title[:80]}")
    if not rows:
        print("nenhuma demanda")
    return 0


def _review_limit(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 200:
        raise argparse.ArgumentTypeError("deve estar entre 1 e 200")
    return number


def _print_review(conn: psycopg.Connection, limit: int, *, only_review: bool) -> int:
    rows = conn.execute(_REVIEW_SQL, (only_review, limit)).fetchall()
    for sent_at, phone, text, sector, kind, urgency, source, needs_review, reason, action in rows:
        snippet = " ".join((text or "(sem texto)").split())[:_REVIEW_TEXT_CHARS]
        label = action if action != "classified" else f"{sector}/{kind}/{urgency}"
        flag = f" [revisar: {reason}]" if needs_review else ""
        print(f"{sent_at:%Y-%m-%d %H:%M} ...{phone[-4:]} | {label} | {source}{flag} | {snippet}")
    if not rows:
        print("nada para mostrar")
    return 0


def _bounded_limit(value: str) -> int:
    number = int(value)
    if not 1 <= number <= MAX_CLASSIFY_LIMIT:
        raise argparse.ArgumentTypeError(f"deve estar entre 1 e {MAX_CLASSIFY_LIMIT}")
    return number


def _classify_pending(conn: psycopg.Connection, limit: int, *, use_llm: bool) -> int:
    runtime_url = os.environ.get("APP_DATABASE_URL")
    if not runtime_url:
        print(
            "APP_DATABASE_URL nao definida: o classify-pending nao roda com a conexao do dono",
            file=sys.stderr,
        )
        return 2
    llm = None
    if use_llm:
        llm, description = build_classifier(os.environ)
        print(description)
    tenants = conn.execute("SELECT id, slug FROM tenants ORDER BY slug").fetchall()
    db = Database(runtime_url)
    db.open()
    failed = 0
    try:
        for tenant_id, slug in tenants:
            try:
                counts = classify_pending(db, tenant_id, llm=llm, limit=limit)
                demands = materialize_demands(db, tenant_id, limit=limit)
            except Exception as exc:
                failed += 1
                print(f"{slug}: erro ({type(exc).__name__})", file=sys.stderr)
                continue
            summary = " ".join(
                f"{name}={counts[name]}"
                for name in ("classified", "noise", "attach_reply", "deferred", "failed")
            )
            work = " ".join(
                f"{name}={demands[name]}" for name in ("created", "attached", "skipped", "failed")
            )
            print(f"{slug}: {summary} | demandas: {work}")
    finally:
        db.close()
    return 1 if failed else 0


def _backfill_appointments(conn: psycopg.Connection) -> int:
    runtime_url = os.environ.get("APP_DATABASE_URL")
    if not runtime_url:
        print("APP_DATABASE_URL nao definida", file=sys.stderr)
        return 2
    db = Database(runtime_url)
    db.open()
    try:
        for tenant_id, slug in conn.execute("SELECT id, slug FROM tenants ORDER BY slug"):
            print(f"{slug}: compromissos criados={backfill_appointments(db, tenant_id)}")
    finally:
        db.close()
    return 0


def _tenant_id(conn: psycopg.Connection, slug: str):
    row = conn.execute("SELECT id FROM tenants WHERE slug = %s", (slug,)).fetchone()
    if row is None:
        print(f"tenant nao encontrado: {slug}", file=sys.stderr)
        return None
    return row[0]


def _add_recipient(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    tenant_id = _tenant_id(conn, args.tenant_slug)
    if tenant_id is None:
        return 1
    phone = re.sub(r"\D", "", args.phone)
    if not 10 <= len(phone) <= 15:
        print("telefone invalido: use DDI e DDD, so numeros (ex.: 5511999990101)", file=sys.stderr)
        return 2
    user_id = None
    if args.user_email:
        row = conn.execute(
            "SELECT id, role FROM users WHERE tenant_id = %s AND lower(email) = lower(%s)",
            (tenant_id, args.user_email),
        ).fetchone()
        if row is None:
            print("usuario nao encontrado neste tenant", file=sys.stderr)
            return 1
        if row[1] != "socio":
            print("o agente so fala com socio: o usuario informado nao e socio", file=sys.stderr)
            return 2
        user_id = row[0]
    try:
        conn.execute(
            "INSERT INTO agent_recipients (tenant_id, user_id, name, phone) "
            "VALUES (%s, %s, %s, %s)",
            (tenant_id, user_id, args.name.strip(), phone),
        )
    except psycopg.errors.UniqueViolation:
        print("telefone ja cadastrado neste tenant", file=sys.stderr)
        return 1
    print(f"destinatario cadastrado: {args.name.strip()} (...{phone[-4:]})")
    return 0


def _remove_recipient(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    tenant_id = _tenant_id(conn, args.tenant_slug)
    if tenant_id is None:
        return 1
    phone = re.sub(r"\D", "", args.phone)
    done = conn.execute(
        "UPDATE agent_recipients SET active = false WHERE tenant_id = %s AND phone = %s",
        (tenant_id, phone),
    )
    print("destinatario desativado" if done.rowcount else "destinatario nao encontrado")
    return 0 if done.rowcount else 1


def _list_recipients(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    tenant_id = _tenant_id(conn, args.tenant_slug)
    if tenant_id is None:
        return 1
    rows = conn.execute(
        "SELECT name, phone, active FROM agent_recipients WHERE tenant_id = %s ORDER BY created_at",
        (tenant_id,),
    ).fetchall()
    for name, phone, active in rows:
        print(f"{name} ...{phone[-4:]} {'ativo' if active else 'desativado'}")
    if not rows:
        print("nenhum destinatario")
    return 0


def _agent_outbox(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    tenant_id = _tenant_id(conn, args.tenant_slug) if args.tenant_slug else None
    if args.tenant_slug and tenant_id is None:
        return 1
    rows = conn.execute(
        "SELECT n.created_at, r.name, n.kind, n.status, n.attempts, n.body "
        "FROM agent_notifications n JOIN agent_recipients r ON r.id = n.recipient_id "
        "WHERE (%s::uuid IS NULL OR n.tenant_id = %s::uuid) "
        "ORDER BY n.created_at DESC, n.id LIMIT %s",
        (tenant_id, tenant_id, args.limit),
    ).fetchall()
    for created, name, kind, status, attempts, body in rows:
        print(f"{created:%Y-%m-%d %H:%M} | {name} | {kind} | {status} ({attempts}x)")
        if body:
            print("    " + body.replace(chr(10), chr(10) + "    "))
    if not rows:
        print("caixa de saida vazia")
    return 0


_AGENT_WEBHOOK_ENV = (
    "EVOLUTION_URL",
    "EVOLUTION_API_KEY",
    "AGENT_INSTANCE",
    "AGENT_APP_URL",
)


def _evolution_from_env() -> EvolutionClient:
    return EvolutionClient(os.environ["EVOLUTION_URL"], os.environ["EVOLUTION_API_KEY"])


def _setup_agent_webhook() -> int:
    missing = [name for name in _AGENT_WEBHOOK_ENV if not os.environ.get(name)]
    if missing:
        print("faltam variaveis no ambiente da api: " + ", ".join(missing), file=sys.stderr)
        return 2
    secret = os.environ.get("AGENT_WEBHOOK_SECRET")
    if not secret:
        print("AGENT_WEBHOOK_SECRET nao esta definido. Gerei um segredo para voce.")
        print("Salve esta linha no ambiente do servico api, faca Implantar e rode de novo:")
        print("AGENT_WEBHOOK_SECRET=" + secrets.token_urlsafe(32))
        return 2
    instance = os.environ["AGENT_INSTANCE"]
    url = os.environ["AGENT_APP_URL"].rstrip("/") + "/webhooks/agent"
    events = ["MESSAGES_UPSERT"]
    client = _evolution_from_env()
    try:
        client.set_webhook(instance, url=url, headers={"X-Webhook-Secret": secret}, events=events)
        stored = client.find_webhook(instance)
    except EvolutionError as exc:
        print(f"a Evolution recusou: {exc}", file=sys.stderr)
        return 1
    stored_events = [str(e).upper() for e in stored.get("events") or []]
    if not (
        stored.get("enabled") and stored.get("url") == url and "MESSAGES_UPSERT" in stored_events
    ):
        print("o webhook gravado na Evolution nao confere com o pedido:", file=sys.stderr)
        print(
            f"  url={stored.get('url')} ativo={stored.get('enabled')} eventos={stored_events}",
            file=sys.stderr,
        )
        return 1
    print(f"webhook configurado na instancia {instance}")
    print(f"  url: {url}")
    print(f"  eventos: {', '.join(events)}")
    print("  cabecalho de seguranca: X-Webhook-Secret (valor nao exibido)")
    return 0


def _read_password() -> str | None:
    password = os.environ.get("USER_PASSWORD")
    if password:
        return password
    if sys.stdin.isatty():
        first = getpass.getpass("Senha: ")
        if first == getpass.getpass("Repita a senha: "):
            return first
        print("as senhas nao conferem", file=sys.stderr)
        return None
    print("USER_PASSWORD nao definida (ou rode num terminal interativo)", file=sys.stderr)
    return None


def _create_user(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    password = _read_password()
    if password is None:
        return 2
    row = conn.execute("SELECT id FROM tenants WHERE slug = %s", (args.tenant_slug,)).fetchone()
    if row is None:
        print(f"tenant nao encontrado: {args.tenant_slug}", file=sys.stderr)
        return 1
    try:
        user_id = create_user(
            conn,
            tenant_id=row[0],
            email=args.email,
            name=args.name,
            role=args.role,
            password=password,
            sectors=tuple(args.sector),
        )
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    except psycopg.errors.UniqueViolation:
        print("ja existe um usuario com esse e-mail neste tenant", file=sys.stderr)
        return 1
    print(f"usuario criado: {user_id} ({args.role})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "setup-agent-webhook":
        return _setup_agent_webhook()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL nao definida", file=sys.stderr)
        return 2

    with psycopg.connect(database_url, autocommit=True) as conn:
        if args.command == "create-tenant":
            tenant_id = create_tenant(conn, slug=args.slug, name=args.name)
            print(f"tenant criado: {tenant_id}")
            return 0

        if args.command == "classify-pending":
            return _classify_pending(conn, args.limit, use_llm=not args.no_llm)

        if args.command == "review":
            return _print_review(conn, args.limit, only_review=args.needs_review)

        if args.command == "create-user":
            return _create_user(conn, args)

        if args.command == "demands":
            return _print_demands(
                conn, args.limit, only_open=args.open, tenant_slug=args.tenant_slug
            )

        if args.command == "add-recipient":
            return _add_recipient(conn, args)

        if args.command == "remove-recipient":
            return _remove_recipient(conn, args)

        if args.command == "recipients":
            return _list_recipients(conn, args)

        if args.command == "agent-outbox":
            return _agent_outbox(conn, args)

        if args.command == "backfill-appointments":
            return _backfill_appointments(conn)

        if args.command == "stats":
            return _print_stats(conn)

        if args.command == "create-runtime-role":
            password = os.environ.get("APP_DB_PASSWORD")
            if not password:
                print("APP_DB_PASSWORD nao definida", file=sys.stderr)
                return 2
            create_runtime_role(conn, password=password)
            print("papel demanda_runtime criado/atualizado")
            return 0

        row = conn.execute("SELECT id FROM tenants WHERE slug = %s", (args.tenant_slug,)).fetchone()
        if row is None:
            print(f"tenant nao encontrado: {args.tenant_slug}", file=sys.stderr)
            return 1
        channel_id, secret = create_channel(
            conn,
            tenant_id=row[0],
            name=args.name,
            instance_name=args.instance,
            listen_groups=args.listen_groups,
        )
        print(f"canal criado: {channel_id}")
        print(f"URL do webhook: /webhooks/evolution/{channel_id}")
        print(f"X-Webhook-Secret (guarde agora, nao sera exibido de novo): {secret}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
