import type { Appointment } from "../../api/types";
import { timeLabel } from "../../lib/agenda";
import { dayKey, monthGrid } from "../../lib/calendar";

const WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];
const SHOWN = 3;

interface Props {
  cursor: Date;
  items: Appointment[];
  onPickDay: (date: Date) => void;
}

export function MonthView({ cursor, items, onPickDay }: Props) {
  const today = dayKey(new Date());
  const grid = monthGrid(cursor);
  return (
    <div className="cal-month">
      {WEEKDAYS.map((name) => (
        <span key={name} className="cal-month-head">
          {name}
        </span>
      ))}
      {grid.map((date) => {
        const events = items.filter((item) => dayKey(new Date(item.starts_at)) === dayKey(date));
        const label = date.getDate() + " de " + date.toLocaleDateString("pt-BR", { month: "long" });
        return (
          <button
            key={dayKey(date)}
            type="button"
            className="cal-cell"
            aria-label={label}
            data-today={dayKey(date) === today}
            data-outside={date.getMonth() !== cursor.getMonth()}
            onClick={() => onPickDay(date)}
          >
            <span className="cal-cell-number num">{date.getDate()}</span>
            {events.slice(0, SHOWN).map((item) => (
              <span key={item.id} className="cal-chip" data-status={item.status}>
                {timeLabel(item) + " " + item.title}
              </span>
            ))}
            {events.length > SHOWN ? <span className="cal-more">{"+" + (events.length - SHOWN) + " mais"}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
