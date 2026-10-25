"""Le dia e hora de compromissos escritos em portugues ("quarta as 14", "dia 28 as 10h30")."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

_WEEKDAYS = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "janeiro",
            "fevereiro",
            "marco",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ),
        start=1,
    )
}

_CLOCK = re.compile(r"\b([01]?\d|2[0-9]):([0-5]\d)\b")
_H = re.compile(r"\b(\d{1,2})\s*h(?:oras?)?\s*([0-5]\d)?\b")
_AS = re.compile(r"\bas\s+(\d{1,2})\b(?!\s*[/:]|\s*de\s)")
_NOON = re.compile(r"\bmeio[\s-]?dia\b")
_FULL_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b")
_DAY_MONTH_NAME = re.compile(r"\bdia\s+(\d{1,2})\s+de\s+([a-z]+)\b")
_DAY_ONLY = re.compile(r"\bdia\s+(\d{1,2})\b")
_WEEKDAY = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")(?!\s+via\b)\b")
_AFTER_TOMORROW = re.compile(r"\bdepois\s+de\s+amanha\b")
_TOMORROW = re.compile(r"\bamanha\b")
_TODAY = re.compile(r"\bhoje\b")


@dataclass(frozen=True)
class When:
    start: datetime  # com fuso; em evento de dia inteiro, 00:00 do dia
    all_day: bool


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _time_of(text: str) -> time | None:
    """Hora citada, ou None. Hora invalida (ex.: 25h) devolve None."""
    for pattern in (_CLOCK, _H, _AS):
        match = pattern.search(text)
        if match:
            hour = int(match.group(1))
            minute = (
                int(match.group(2))
                if match.lastindex and match.lastindex >= 2 and match.group(2)
                else 0
            )
            return time(hour, minute) if hour < 24 else None
    if _NOON.search(text):
        return time(12, 0)
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _next_day_of_month(day: int, today: date) -> date | None:
    year, month = today.year, today.month
    for _ in range(13):
        found = _safe_date(year, month, day)
        if found and found >= today:
            return found
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return None


def _next_occurrence(month: int, day: int, today: date) -> date | None:
    for year in (today.year, today.year + 1):
        found = _safe_date(year, month, day)
        if found and found >= today:
            return found
    return None


def _date_of(text: str, today: date) -> date | None:
    match = _FULL_DATE.search(text)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
        if year:
            full_year = int(year) + (2000 if len(year) == 2 else 0)
            return _safe_date(full_year, month, day)
        return _next_occurrence(month, day, today)
    match = _DAY_MONTH_NAME.search(text)
    if match and match.group(2) in _MONTHS:
        return _next_occurrence(_MONTHS[match.group(2)], int(match.group(1)), today)
    match = _DAY_ONLY.search(text)
    if match:
        return _next_day_of_month(int(match.group(1)), today)
    if _AFTER_TOMORROW.search(text):
        return today + timedelta(days=2)
    if _TOMORROW.search(text):
        return today + timedelta(days=1)
    if _TODAY.search(text):
        return today
    match = _WEEKDAY.search(text)
    if match:
        delta = (_WEEKDAYS[match.group(1)] - today.weekday()) % 7
        return today + timedelta(days=delta or 7)
    return None


def extract_when(text: str, reference: datetime) -> When | None:
    """Dia e hora citados em `text`, contando a partir de `reference` (hora local do escritorio).

    Sem dia reconhecivel devolve None. Com dia e sem hora, vira evento de dia inteiro.
    """
    plain = _plain(text or "")
    found = _date_of(plain, reference.date())
    if found is None:
        return None
    clock = _time_of(plain)
    if clock is None and (_CLOCK.search(plain) or _H.search(plain) or _AS.search(plain)):
        return None  # citou uma hora, mas invalida (ex.: 25h)
    if clock is None:
        return When(datetime.combine(found, time(0, 0), tzinfo=reference.tzinfo), True)
    return When(datetime.combine(found, clock, tzinfo=reference.tzinfo), False)
