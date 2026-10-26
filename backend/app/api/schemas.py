from datetime import date, datetime
from typing import Annotated, ClassVar, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Status = Literal["novo", "em_andamento", "aguardando", "concluido"]
Sector = Literal["triagem", "fiscal", "contabil", "dp", "societario", "financeiro", "rh-interno"]
Kind = Literal["tarefa", "compromisso", "duvida", "documento", "cobranca", "reclamacao", "nota"]
Urgency = Literal["normal", "alta", "critica"]
ContactKind = Literal["cliente", "fornecedor", "colaborador", "desconhecido"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PersonRef(BaseModel):
    id: UUID
    name: str


class ContactRef(BaseModel):
    id: UUID
    name: str | None
    phone: str
    kind: str


class Progress(BaseModel):
    done: int
    total: int
    percent: int


class Card(BaseModel):
    id: UUID
    title: str
    sector: str
    kind: str
    urgency: str
    status: str
    due_date: date | None
    origin: str
    assignee: PersonRef | None
    contact: ContactRef | None
    progress: Progress
    messages_count: int
    created_at: datetime
    last_activity_at: datetime
    closed_at: datetime | None
    idle_hours: int


class MessageOut(BaseModel):
    id: UUID
    direction: str
    text: str | None
    type: str
    sent_at: datetime


class SubtaskOut(BaseModel):
    id: UUID
    title: str
    done: bool


class Detail(Card):
    messages: list[MessageOut]
    subtasks: list[SubtaskOut]


class Column(BaseModel):
    status: str
    count: int
    demands: list[Card]


class Board(BaseModel):
    columns: list[Column]


class DemandCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    sector: Sector
    kind: Kind = "tarefa"
    urgency: Urgency = "normal"
    due_date: date | None = None
    assignee_id: UUID | None = None
    contact_id: UUID | None = None


class _AtLeastOneField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # campos que podem ser omitidos, mas nunca enviados como null
    not_nullable: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _check_fields(self):
        if not self.model_fields_set:
            raise ValueError("informe pelo menos um campo")
        for name in self.not_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} nao pode ser null")
        return self


class DemandPatch(_AtLeastOneField):
    not_nullable: ClassVar[tuple[str, ...]] = ("title", "status", "urgency", "sector")

    title: Title | None = None
    status: Status | None = None
    urgency: Urgency | None = None
    sector: Sector | None = None
    due_date: date | None = None
    assignee_id: UUID | None = None


class SubtaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title


class SubtaskPatch(_AtLeastOneField):
    not_nullable: ClassVar[tuple[str, ...]] = ("title", "done")

    title: Title | None = None
    done: bool | None = None


class ContactPatch(_AtLeastOneField):
    not_nullable: ClassVar[tuple[str, ...]] = ("name", "kind")

    name: PersonName | None = None
    kind: ContactKind | None = None


class UserOut(BaseModel):
    id: UUID
    name: str
    role: str
    sectors: list[str] = Field(default_factory=list)


AppointmentStatus = Literal["proposed", "confirmed", "cancelled"]


class AppointmentOut(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    all_day: bool
    status: str
    demand_id: UUID
    sector: str
    contact: ContactRef | None


class AppointmentPatch(_AtLeastOneField):
    not_nullable: ClassVar[tuple[str, ...]] = ("status", "starts_at", "all_day", "title")

    status: AppointmentStatus | None = None
    starts_at: AwareDatetime | None = None
    all_day: bool | None = None
    title: Title | None = None
