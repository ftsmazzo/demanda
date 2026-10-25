"""Quem enxerga e quem altera cada demanda (3 papeis fixos no MVP)."""

from app.core.users import CurrentUser

HR_SECTOR = "rh-interno"


def can_access_hr(user: CurrentUser) -> bool:
    """RH interno: so socios e quem tem o setor rh-interno (mesmo que a demanda seja atribuida)."""
    return user.role == "socio" or HR_SECTOR in user.sectors


def visibility_clause(user: CurrentUser, alias: str = "d") -> tuple[str, list]:
    """Fragmento SQL (e parametros) com as demandas que o usuario pode ver.

    socio: tudo; gestor: seus setores ou o que for atribuido a ele; colaborador: so o atribuido.
    """
    if user.role == "socio":
        base, params = "TRUE", []
    elif user.role == "gestor":
        base = f"({alias}.sector = ANY(%s) OR {alias}.assignee_id = %s)"
        params = [list(user.sectors), user.id]
    else:
        base, params = f"{alias}.assignee_id = %s", [user.id]
    if not can_access_hr(user):
        return f"({base}) AND {alias}.sector <> '{HR_SECTOR}'", params
    return base, params


def can_create_in(user: CurrentUser, sector: str) -> bool:
    if user.role == "socio":
        return True
    return user.role == "gestor" and sector in user.sectors
