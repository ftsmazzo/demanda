-- Mensagens que nao viram demanda (ex.: "ok" sem demanda aberta) sao registradas para nao voltarem
-- a fila a cada execucao.
CREATE TABLE skipped_messages (
    tenant_id  uuid NOT NULL,
    message_id uuid PRIMARY KEY,
    reason     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (message_id, tenant_id) REFERENCES messages (id, tenant_id)
);

GRANT SELECT, INSERT ON skipped_messages TO demanda_app;
ALTER TABLE skipped_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE skipped_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY skipped_messages_isolation ON skipped_messages
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

-- A aplicacao nao precisa ler hashes de senha: o login usa auth_user (SECURITY DEFINER).
REVOKE SELECT ON users FROM demanda_app;
GRANT SELECT (id, tenant_id, email, name, role, active, created_at) ON users TO demanda_app;
