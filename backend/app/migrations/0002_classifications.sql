-- Classificacao das mensagens (regras + IA). Historico append-only por versao de regras.

ALTER TABLE messages ADD CONSTRAINT messages_id_tenant_key UNIQUE (id, tenant_id);

CREATE TABLE message_classifications (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants (id),
    message_id    uuid NOT NULL,
    action        text NOT NULL CHECK (action IN ('classified', 'attach_reply', 'noise')),
    sector        text NOT NULL CHECK (
        sector IN ('triagem', 'fiscal', 'contabil', 'dp', 'societario', 'financeiro', 'rh-interno')
    ),
    kind          text NOT NULL CHECK (
        kind IN ('tarefa', 'compromisso', 'duvida', 'documento', 'cobranca', 'reclamacao',
                 'ruido', 'indefinido')
    ),
    urgency       text NOT NULL CHECK (urgency IN ('normal', 'alta', 'critica')),
    client_hint   text,
    confidence    real NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source        text NOT NULL CHECK (source IN ('rule', 'llm', 'fallback')),
    needs_review  boolean NOT NULL DEFAULT false,
    reason        text,
    model         text,
    rules_version text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    -- uma classificacao por mensagem e versao de regras (permite reprocessar com versao nova)
    UNIQUE (message_id, rules_version),
    -- a classificacao so pode apontar para mensagem do mesmo tenant
    FOREIGN KEY (message_id, tenant_id) REFERENCES messages (id, tenant_id)
);

CREATE INDEX message_classifications_review_idx
    ON message_classifications (tenant_id, created_at DESC) WHERE needs_review;

GRANT SELECT, INSERT ON message_classifications TO demanda_app;

ALTER TABLE message_classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_classifications FORCE ROW LEVEL SECURITY;

CREATE POLICY message_classifications_isolation ON message_classifications
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));
