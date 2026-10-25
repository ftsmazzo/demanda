import { useState, type FormEvent } from "react";
import type { Detail } from "../../api/types";
import { Icon } from "../../components/Icon";
import { useAddSubtask, useToggleSubtask } from "../../hooks/demand";
import { saveErrorMessage } from "../../lib/errors";

export function Steps({ demand }: { demand: Detail }) {
  const toggle = useToggleSubtask(demand.id);
  const add = useAddSubtask(demand.id);
  const [title, setTitle] = useState("");
  const { done, total, percent } = demand.progress;
  const failure = toggle.error ?? add.error;

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = title.trim();
    if (!text || add.isPending) return;
    add.mutate(text, { onSuccess: () => setTitle("") });
  }

  return (
    <section aria-labelledby="steps-title">
      <h3 className="section-title" id="steps-title">
        Etapas <span>{total ? `${done} de ${total}` : "nenhuma ainda"}</span>
      </h3>
      {total ? (
        <div
          className="progress"
          role="progressbar"
          aria-label="Progresso das etapas"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <i style={{ width: `${percent}%` }} />
        </div>
      ) : null}
      <ul className="checklist">
        {demand.subtasks.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className="check"
              role="checkbox"
              aria-checked={item.done}
              onClick={() => toggle.mutate({ id: item.id, done: !item.done })}
            >
              <span className="box">
                <Icon name="check" size={13} />
              </span>
              <span className="check-text">{item.title}</span>
            </button>
          </li>
        ))}
      </ul>
      <form className="add-step" onSubmit={submit}>
        <input
          className="input input-compact"
          aria-label="Nova etapa"
          placeholder="Nova etapa"
          maxLength={200}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <button className="btn" type="submit" disabled={add.isPending || !title.trim()}>
          Adicionar
        </button>
      </form>
      {failure ? (
        <p role="alert" className="form-error">
          {saveErrorMessage(failure)}
        </p>
      ) : null}
    </section>
  );
}
