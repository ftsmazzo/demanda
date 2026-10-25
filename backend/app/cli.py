"""CLI administrativa: python -m app.cli <comando>. Usa DATABASE_URL (papel dono do schema)."""

import argparse
import os
import sys

import psycopg

from app.classification.factory import build_classifier
from app.classification.store import classify_pending
from app.db import Database
from app.provisioning import create_channel, create_runtime_role, create_tenant

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
    FROM message_classifications c JOIN messages m ON m.id = c.message_id
    WHERE (NOT %s OR c.needs_review)
    ORDER BY m.provider_timestamp DESC
    LIMIT %s
"""
_REVIEW_TEXT_CHARS = 90


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
            except Exception as exc:
                failed += 1
                print(f"{slug}: erro ({type(exc).__name__})", file=sys.stderr)
                continue
            summary = " ".join(
                f"{name}={counts[name]}"
                for name in ("classified", "noise", "attach_reply", "deferred", "failed")
            )
            print(f"{slug}: {summary}")
    finally:
        db.close()
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
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
