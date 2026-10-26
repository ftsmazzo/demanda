-- Agente em linguagem natural: acoes pendentes de confirmacao, novos tipos de historico e
-- contador de uso da IA separado por finalidade (caso x agente).
CREATE TABLE agent_pending_actions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenants (id),
    recipient_id uuid NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('create_task', 'assign', 'set_status', 'mark_priority')),
    payload      jsonb NOT NULL,
    summary      text NOT NULL,
    status       text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'done', 'cancelled', 'expired', 'superseded')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    resolved_at  timestamptz,
    FOREIGN KEY (recipient_id, tenant_id) REFERENCES agent_recipients (id, tenant_id)
);
CREATE INDEX agent_pending_actions_open_idx ON agent_pending_actions (recipient_id, status)
    WHERE status = 'pending';

GRANT SELECT, INSERT, UPDATE ON agent_pending_actions TO demanda_app;
ALTER TABLE agent_pending_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_pending_actions FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_pending_actions_isolation ON agent_pending_actions
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

DO $$
DECLARE
    item record;
BEGIN
    FOR item IN
        SELECT conname FROM pg_constraint
        WHERE contype = 'c' AND conrelid = 'case_events'::regclass
          AND pg_get_constraintdef(oid) LIKE '%appointment_updated%'
    LOOP
        EXECUTE format('ALTER TABLE case_events DROP CONSTRAINT %I', item.conname);
    END LOOP;
END
$$;
ALTER TABLE case_events ADD CONSTRAINT case_events_kind_check CHECK (
    kind IN ('created', 'attached', 'summary', 'appointment_created', 'appointment_updated',
             'proposal', 'merged', 'split', 'review', 'assigned', 'status_changed')
);

ALTER TABLE ai_usage ADD COLUMN purpose text NOT NULL DEFAULT 'case';
ALTER TABLE ai_usage DROP CONSTRAINT ai_usage_pkey;
ALTER TABLE ai_usage ADD PRIMARY KEY (tenant_id, day, purpose);
