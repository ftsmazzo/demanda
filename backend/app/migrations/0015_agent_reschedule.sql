-- O agente passa a propor remarcacao de compromisso (o socio confirma com 1).
ALTER TABLE agent_pending_actions DROP CONSTRAINT agent_pending_actions_kind_check;
ALTER TABLE agent_pending_actions ADD CONSTRAINT agent_pending_actions_kind_check CHECK (
    kind IN ('create_task', 'assign', 'set_status', 'mark_priority', 'reschedule')
);
