"""Textos das mensagens do agente aos socios. Os numeros vem de consultas; aqui so se escreve."""

from dataclasses import dataclass, field
from datetime import date, datetime

_WEEKDAYS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


@dataclass(frozen=True)
class AppointmentInfo:
    title: str
    starts_at: datetime  # na hora local do escritorio
    all_day: bool
    contact_name: str | None
    sector: str


@dataclass(frozen=True)
class StuckItem:
    title: str
    sector: str
    idle_hours: int


@dataclass(frozen=True)
class SummaryData:
    day: date
    created_today: int
    closed_today: int
    open_total: int
    critical_open: int
    stuck: list[StuckItem] = field(default_factory=list)
    tomorrow: list[tuple[str, str]] = field(default_factory=list)  # (hora, titulo)


def _day(value: date) -> str:
    return f"{_WEEKDAYS[value.weekday()]}, {value:%d/%m}"


def _idle(hours: int) -> str:
    if hours >= 48:
        return f"{hours // 24} dias"
    if hours >= 24:
        return "1 dia"
    return f"{max(hours, 1)} h"


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def when_text(starts_at: datetime, all_day: bool) -> str:
    day = _day(starts_at.date())
    return day + (" o dia todo" if all_day else f" às {starts_at:%H:%M}")


def appointment_text(info: AppointmentInfo, app_url: str) -> str:
    when = when_text(info.starts_at, info.all_day)
    sector = "" if info.sector == "Triagem" else f" ({info.sector})"
    who = (
        f"{info.contact_name} falou de um compromisso" if info.contact_name else "Novo compromisso"
    )
    return (
        f"*{who}*\n"
        f"{info.title}\n"
        f"Quando: {when}{sector}\n\n"
        "Responda 1 para confirmar ou 2 para cancelar.\n"
        f"Ou use a Agenda: {app_url.rstrip('/')}/agenda"
    )


def summary_text(data: SummaryData, app_url: str) -> str:
    lines = [f"*Resumo do dia, {_day(data.day)}*"]
    lines.append(
        f"Hoje: {_plural(data.created_today, 'nova', 'novas')}, "
        f"{_plural(data.closed_today, 'concluída', 'concluídas')}."
    )
    open_line = (
        f"Em aberto: {data.open_total} abertas" if data.open_total != 1 else "Em aberto: 1 aberta"
    )
    if data.critical_open:
        open_line += f", {_plural(data.critical_open, 'crítica', 'críticas')}"
    lines.append(open_line + ".")
    if data.stuck:
        lines.append("\n*Mais paradas*")
        lines.extend(
            f"- {item.title} ({item.sector}, {_idle(item.idle_hours)})" for item in data.stuck
        )
    if data.tomorrow:
        lines.append("\n*Amanhã*")
        lines.extend(f"- {hour} {title}" for hour, title in data.tomorrow)
    lines.append(f"\nAbra o quadro: {app_url.rstrip('/')}/")
    return "\n".join(lines)


def stuck_text(items: list[StuckItem], app_url: str) -> str:
    lines = ["*Demandas paradas há mais tempo*"]
    lines.extend(
        f"{number}. {item.title} ({item.sector}, parada há {_idle(item.idle_hours)})"
        for number, item in enumerate(items, start=1)
    )
    lines.append(f"\nAbra o quadro: {app_url.rstrip('/')}/")
    return "\n".join(lines)


def confirmed_text(title: str, when: str) -> str:
    return f"Confirmado: {title}\n{when}."


def cancelled_text(title: str, when: str) -> str:
    return f"Cancelado: {title}\n{when}."


def already_text(title: str, status: str) -> str:
    state = "confirmado" if status == "confirmed" else "cancelado"
    return f"Esse compromisso já estava {state}: {title}."


def nothing_to_confirm_text(app_url: str) -> str:
    return (
        f"Não há compromisso esperando sua resposta.\nVeja a Agenda: {app_url.rstrip('/')}/agenda"
    )


def nothing_stuck_text() -> str:
    return "Nada parado há mais de 1 dia. Tudo andando."


def agenda_text(today: list[tuple[str, str]], tomorrow: list[tuple[str, str]], app_url: str) -> str:
    if not today and not tomorrow:
        return "Nenhum compromisso hoje ou amanhã."
    lines = ["*Sua agenda*"]
    for label, items in (("Hoje", today), ("Amanhã", tomorrow)):
        if items:
            lines.append("\n*" + label + "*")
            lines.extend(f"- {hour} {title}" for hour, title in items)
    lines.append(f"\nAgenda completa: {app_url.rstrip('/')}/agenda")
    return "\n".join(lines)


def help_text(app_url: str) -> str:
    return (
        "*O que eu faço*\n"
        "1 - confirmar o compromisso que acabei de avisar\n"
        "2 - cancelar esse compromisso\n"
        "parado - listar as demandas paradas há mais tempo\n"
        "agenda - seus compromissos de hoje e de amanhã\n\n"
        f"Quadro completo: {app_url.rstrip('/')}/"
    )


def unknown_text() -> str:
    return "Não entendi. Responda *ajuda* para ver o que eu faço."
