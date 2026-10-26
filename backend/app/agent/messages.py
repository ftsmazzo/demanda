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


def appointment_text(info: AppointmentInfo, app_url: str) -> str:
    when = _day(info.starts_at.date())
    when += " o dia todo" if info.all_day else f" às {info.starts_at:%H:%M}"
    who = (
        f"{info.contact_name} falou de um compromisso" if info.contact_name else "Novo compromisso"
    )
    return (
        f"*{who}*\n"
        f"{info.title}\n"
        f"Quando: {when} ({info.sector})\n\n"
        f"Confirme ou cancele na Agenda: {app_url.rstrip('/')}/agenda"
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
