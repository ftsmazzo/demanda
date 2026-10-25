-- Compromissos (reunioes, horarios marcados) lidos das mensagens. Nascem "proposed" e um
-- socio ou gestor confirma ou cancela.
CREATE TABLE appointments (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenants (id),
    demand_id         uuid NOT NULL,
    contact_id        uuid,
    source_message_id uuid,
    title             text NOT NULL,
    starts_at         timestamptz NOT NULL,
    all_day           boolean NOT NULL DEFAULT false,
    status            text NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'confirmed', 'cancelled')),
    origin            text NOT NULL DEFAULT 'auto' CHECK (origin IN ('auto', 'manual')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id),
    -- idempotencia: uma mensagem gera no maximo um compromisso
    UNIQUE (source_message_id),
    FOREIGN KEY (demand_id, tenant_id) REFERENCES demands (id, tenant_id),
    FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
    FOREIGN KEY (source_message_id, tenant_id) REFERENCES messages (id, tenant_id)
);
CREATE INDEX appointments_agenda_idx ON appointments (tenant_id, starts_at);

GRANT SELECT, INSERT, UPDATE ON appointments TO demanda_app;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments FORCE ROW LEVEL SECURITY;
CREATE POLICY appointments_isolation ON appointments
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));
