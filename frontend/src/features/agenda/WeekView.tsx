import type { CSSProperties } from "react";
import type { Appointment } from "../../api/types";
import { timeLabel } from "../../lib/agenda";
import { dayKey, layoutDay, weekDays } from "../../lib/calendar";

const FROM = 6;
const TO = 20;
const HOURS = Array.from({ length: TO - FROM }, (_, i) => FROM + i);

export const dayName = (date: Date) =>
  date.toLocaleDateString("pt-BR", { weekday: "long" }) +
  ", " +
  date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

interface Props {
  cursor: Date;
  items: Appointment[];
  selectedId: string | null;
  onSelect: (item: Appointment) => void;
}

export function WeekView({ cursor, items, selectedId, onSelect }: Props) {
  const days = weekDays(cursor);
  const today = dayKey(new Date());
  const byDay = (date: Date, allDay: boolean) =>
    items.filter((item) => dayKey(new Date(item.starts_at)) === dayKey(date) && item.all_day === allDay);
  const eventButton = (item: Appointment, style?: CSSProperties) => (
    <button
      key={item.id}
      type="button"
      className="cal-event"
      data-status={item.status}
      data-selected={item.id === selectedId}
      style={style}
      onClick={() => onSelect(item)}
    >
      <span className="cal-event-time num">{timeLabel(item)}</span>{" "}
      <span className="cal-event-title">{item.title}</span>
    </button>
  );

  return (
    <div className="cal-week">
      <div className="cal-head">
        <span />
        {days.map((date) => (
          <span key={dayKey(date)} className="cal-day-head" data-today={dayKey(date) === today}>
            <span>{date.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "")}</span>
            <strong className="num">{date.getDate()}</strong>
          </span>
        ))}
      </div>
      <div className="cal-allday">
        <span className="cal-gutter">dia todo</span>
        {days.map((date) => (
          <div key={dayKey(date)} role="group" aria-label={dayName(date) + " o dia todo"} className="cal-allday-cell">
            {byDay(date, true).map((item) => eventButton(item))}
          </div>
        ))}
      </div>
      <div className="cal-body">
        <div className="cal-hours" aria-hidden="true">
          {HOURS.map((hour) => (
            <span key={hour} className="cal-hour num">
              {String(hour).padStart(2, "0")}:00
            </span>
          ))}
        </div>
        {days.map((date) => (
          <div
            key={dayKey(date)}
            role="group"
            aria-label={dayName(date)}
            className="cal-col"
            data-today={dayKey(date) === today}
          >
            {layoutDay(byDay(date, false), FROM, TO).map((placed) =>
              eventButton(placed.item, {
                top: placed.top + "%",
                height: placed.height + "%",
                left: (placed.lane / placed.lanes) * 100 + "%",
                width: 100 / placed.lanes + "%",
              }),
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
