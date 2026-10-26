-- O agente passa a escrever rascunhos de pedido; o socio aprova com 1 e repassa o texto.
ALTER TABLE agent_pending_actions DROP CONSTRAINT agent_pending_actions_kind_check;
ALTER TABLE agent_pending_actions ADD CONSTRAINT agent_pending_actions_kind_check CHECK (
    kind IN ('create_task', 'assign', 'set_status', 'mark_priority', 'reschedule', 'draft_message')
);
