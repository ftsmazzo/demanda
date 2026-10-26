-- Agente dos socios: quem recebe (so socios) e a caixa de saida, que tambem garante que o
-- mesmo aviso nao sai duas vezes.
CREATE TABLE agent_recipients (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenants (id),
    user_id    uuid,
    name       text NOT NULL,
    phone      text NOT NULL CHECK (phone ~ '^[0-9]{10,15}$'),
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, phone),
    FOREIGN KEY (user_id, tenant_id) REFERENCES users (id, tenant_id)
);

CREATE TABLE agent_notifications (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants (id),
    recipient_id    uuid NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('appointment', 'daily_summary', 'stuck')),
    dedupe_key      text NOT NULL,
    body            text NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'dry_run', 'failed', 'skipped')),
    attempts        integer NOT NULL DEFAULT 0,
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_attempt_at timestamptz,
    sent_at         timestamptz,
    -- idempotencia: o mesmo aviso, para a mesma pessoa, so existe uma vez
    UNIQUE (tenant_id, recipient_id, kind, dedupe_key),
    FOREIGN KEY (recipient_id, tenant_id) REFERENCES agent_recipients (id, tenant_id)
);
CREATE INDEX agent_notifications_open_idx ON agent_notifications (tenant_id, status)
    WHERE status IN ('pending', 'failed');

GRANT SELECT ON agent_recipients TO demanda_app;
GRANT SELECT, INSERT, UPDATE ON agent_notifications TO demanda_app;

ALTER TABLE agent_recipients ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_recipients FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_recipients_isolation ON agent_recipients
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

ALTER TABLE agent_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_notifications FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_notifications_isolation ON agent_notifications
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));
