"""Cadastro de uma empresa nova: empresa, canal de WhatsApp, webhook, socio e agente, de uma vez."""

import re
import secrets
from dataclasses import dataclass
from uuid import UUID

import psycopg

from app.evolution_client import EvolutionClient, EvolutionError
from app.provisioning import create_channel, create_tenant, create_user, hash_secret
from app.security.passwords import MIN_PASSWORD_LENGTH

EVENTS = ["MESSAGES_UPSERT"]
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
_INSTANCE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}$")


class OnboardingError(Exception):
    """Entrada invalida ou algo que impede o cadastro; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class Onboarded:
    tenant_id: UUID
    channel_id: UUID
    webhook_url: str
    owner_password: str | None  # so quando foi gerada aqui


def webhook_url(app_url: str, channel_id: UUID) -> str:
    return f"{app_url.rstrip('/')}/webhooks/evolution/{channel_id}"


def digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def validate(slug: str, instance: str, phone: str, password: str | None) -> str:
    if not _SLUG.match(slug):
        raise OnboardingError("slug invalido: use minusculas, numeros e hifen (2 a 40 caracteres)")
    if not _INSTANCE.match(instance):
        raise OnboardingError("nome de instancia invalido")
    clean = digits(phone)
    if not 10 <= len(clean) <= 15:
        raise OnboardingError("telefone invalido: use DDI e DDD, so numeros (ex.: 5511999990101)")
    if password is not None and len(password) < MIN_PASSWORD_LENGTH:
        raise OnboardingError(f"a senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
    return clean


def rotate_and_set_webhook(
    conn: psycopg.Connection,
    client: EvolutionClient,
    *,
    channel_id: UUID,
    instance: str,
    app_url: str,
) -> str:
    """Troca o segredo do canal e liga o webhook na Evolution.

    A Evolution vem primeiro e e conferida; so depois o hash novo vai para o banco. Se ela
    recusar, o segredo antigo continua valendo e nada se perde.
    """
    secret = secrets.token_urlsafe(32)
    url = webhook_url(app_url, channel_id)
    client.set_webhook(instance, url=url, headers={"X-Webhook-Secret": secret}, events=EVENTS)
    stored = client.find_webhook(instance)
    events = [str(e).upper() for e in stored.get("events") or []]
    if not (stored.get("enabled") and stored.get("url") == url and "MESSAGES_UPSERT" in events):
        raise EvolutionError("o webhook gravado na Evolution nao confere com o pedido")
    conn.execute(
        "UPDATE channels SET webhook_secret_hash = %s WHERE id = %s",
        (hash_secret(secret), channel_id),
    )
    return url


def onboard_tenant(
    conn: psycopg.Connection,
    client: EvolutionClient,
    *,
    slug: str,
    name: str,
    instance: str,
    owner_name: str,
    owner_email: str,
    owner_phone: str,
    password: str | None,
    app_url: str,
    channel_name: str = "WhatsApp do escritorio",
) -> Onboarded:
    phone = validate(slug, instance, owner_phone, password)
    if conn.execute("SELECT 1 FROM tenants WHERE slug = %s", (slug,)).fetchone():
        raise OnboardingError(f"ja existe uma empresa com o slug {slug}")
    owner_password = password or secrets.token_urlsafe(12)

    with conn.transaction():
        tenant_id = create_tenant(conn, slug=slug, name=name)
        channel_id, _ = create_channel(
            conn, tenant_id=tenant_id, name=channel_name, instance_name=instance
        )
        user_id = create_user(
            conn,
            tenant_id=tenant_id,
            email=owner_email,
            name=owner_name,
            role="socio",
            password=owner_password,
        )
        conn.execute(
            "INSERT INTO agent_recipients (tenant_id, user_id, name, phone) "
            "VALUES (%s, %s, %s, %s)",
            (tenant_id, user_id, owner_name.strip(), phone),
        )

    url = rotate_and_set_webhook(
        conn, client, channel_id=channel_id, instance=instance, app_url=app_url
    )
    return Onboarded(tenant_id, channel_id, url, None if password else owner_password)
