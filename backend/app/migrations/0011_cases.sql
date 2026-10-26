-- Etapa 1: a demanda vira o "caso" (titulo e resumo escritos pela IA, proximo passo, revisao)
-- e ganha historico. Ver docs/etapa-1-casos.md.
ALTER TABLE demands
    ADD COLUMN summary       text,
    ADD COLUMN next_step     text,
    ADD COLUMN needs_review  boolean NOT NULL DEFAULT false,
    ADD COLUMN review_reason text,
    ADD COLUMN ai_updated_at timestamptz;

ALTER TABLE demands DROP CONSTRAINT demands_kind_check;
ALTER TABLE demands ADD CONSTRAINT demands_kind_check CHECK (
    kind IN ('tarefa', 'compromisso', 'duvida', 'documento', 'cobranca', 'reclamacao',
             'ruido', 'indefinido', 'nota')
);

CREATE TABLE case_events (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenants (id),
    demand_id  uuid NOT NULL,
    message_id uuid,
    actor      text NOT NULL CHECK (actor IN ('ai', 'rules', 'user')),
    kind       text NOT NULL CHECK (
        kind IN ('created', 'attached', 'summary', 'appointment_created',
                 'appointment_updated', 'proposal', 'merged', 'split', 'review')
    ),
    data       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (demand_id, tenant_id) REFERENCES demands (id, tenant_id),
    FOREIGN KEY (message_id, tenant_id) REFERENCES messages (id, tenant_id)
);
CREATE INDEX case_events_demand_idx ON case_events (demand_id, created_at);

GRANT SELECT, INSERT ON case_events TO demanda_app;
ALTER TABLE case_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_events FORCE ROW LEVEL SECURITY;
CREATE POLICY case_events_isolation ON case_events
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

-- Teto de custo: quantas chamadas de IA de caso cada tenant fez em cada dia.
CREATE TABLE ai_usage (
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    day       date NOT NULL,
    calls     integer NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, day)
);

GRANT SELECT, INSERT, UPDATE ON ai_usage TO demanda_app;
ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_usage FORCE ROW LEVEL SECURITY;
CREATE POLICY ai_usage_isolation ON ai_usage
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));
