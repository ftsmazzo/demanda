-- Nucleo do produto: usuarios, contatos, demandas, subtarefas. RLS por tenant em tudo.
-- O backfill de contatos abaixo le e atualiza messages (FORCE RLS): exige dono do schema com
-- BYPASSRLS ou superusuario, como nas migrations anteriores.

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants (id),
    email         text NOT NULL,
    name          text NOT NULL,
    role          text NOT NULL CHECK (role IN ('socio', 'gestor', 'colaborador')),
    password_hash text NOT NULL,
    active        boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id)
);
CREATE UNIQUE INDEX users_email_idx ON users (tenant_id, lower(email));

CREATE TABLE user_sectors (
    user_id   uuid NOT NULL,
    tenant_id uuid NOT NULL,
    sector    text NOT NULL CHECK (
        sector IN ('triagem', 'fiscal', 'contabil', 'dp', 'societario', 'financeiro', 'rh-interno')
    ),
    PRIMARY KEY (user_id, sector),
    FOREIGN KEY (user_id, tenant_id) REFERENCES users (id, tenant_id)
);

CREATE TABLE contacts (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenants (id),
    phone      text NOT NULL,
    name       text,
    kind       text NOT NULL DEFAULT 'desconhecido'
        CHECK (kind IN ('cliente', 'fornecedor', 'colaborador', 'desconhecido')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, phone),
    UNIQUE (id, tenant_id)
);

ALTER TABLE messages ADD COLUMN contact_id uuid;
ALTER TABLE messages
    ADD CONSTRAINT messages_contact_fk
    FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id);
CREATE INDEX messages_contact_id_idx ON messages (contact_id);

-- Backfill: um contato por telefone ja visto (nome vem da mensagem recebida mais recente).
INSERT INTO contacts (tenant_id, phone, name)
SELECT DISTINCT ON (tenant_id, contact_phone) tenant_id, contact_phone, push_name
FROM messages
WHERE direction = 'in'
ORDER BY tenant_id, contact_phone, provider_timestamp DESC
ON CONFLICT (tenant_id, phone) DO NOTHING;

INSERT INTO contacts (tenant_id, phone)
SELECT DISTINCT tenant_id, contact_phone FROM messages
ON CONFLICT (tenant_id, phone) DO NOTHING;

UPDATE messages m SET contact_id = c.id
FROM contacts c
WHERE c.tenant_id = m.tenant_id AND c.phone = m.contact_phone AND m.contact_id IS NULL;

CREATE TABLE demands (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants (id),
    contact_id       uuid,
    sector           text NOT NULL CHECK (
        sector IN ('triagem', 'fiscal', 'contabil', 'dp', 'societario', 'financeiro', 'rh-interno')
    ),
    kind             text NOT NULL CHECK (
        kind IN ('tarefa', 'compromisso', 'duvida', 'documento', 'cobranca', 'reclamacao',
                 'ruido', 'indefinido')
    ),
    urgency          text NOT NULL CHECK (urgency IN ('normal', 'alta', 'critica')),
    status           text NOT NULL DEFAULT 'novo'
        CHECK (status IN ('novo', 'em_andamento', 'aguardando', 'concluido')),
    title            text NOT NULL,
    assignee_id      uuid,
    due_date         date,
    origin           text NOT NULL DEFAULT 'auto' CHECK (origin IN ('auto', 'manual')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    closed_at        timestamptz,
    UNIQUE (id, tenant_id),
    FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
    FOREIGN KEY (assignee_id, tenant_id) REFERENCES users (id, tenant_id),
    CHECK ((status = 'concluido') = (closed_at IS NOT NULL))
);
CREATE INDEX demands_board_idx ON demands (tenant_id, status, sector);
CREATE INDEX demands_open_contact_idx ON demands (tenant_id, contact_id) WHERE status <> 'concluido';

CREATE TABLE demand_messages (
    tenant_id  uuid NOT NULL,
    demand_id  uuid NOT NULL,
    message_id uuid NOT NULL,
    linked_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (demand_id, message_id),
    UNIQUE (message_id),
    FOREIGN KEY (demand_id, tenant_id) REFERENCES demands (id, tenant_id),
    FOREIGN KEY (message_id, tenant_id) REFERENCES messages (id, tenant_id)
);

CREATE TABLE subtasks (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL,
    demand_id  uuid NOT NULL,
    title      text NOT NULL,
    done       boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (demand_id, tenant_id) REFERENCES demands (id, tenant_id)
);
CREATE INDEX subtasks_demand_idx ON subtasks (demand_id);

GRANT SELECT ON users, user_sectors TO demanda_app;
GRANT SELECT, INSERT, UPDATE ON contacts, demands TO demanda_app;
GRANT SELECT, INSERT ON demand_messages TO demanda_app;
GRANT SELECT, INSERT, UPDATE ON subtasks TO demanda_app;

-- users e user_sectors sem FORCE: auth_user (SECURITY DEFINER, dono) precisa le-las sem tenant.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sectors ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_isolation ON users USING (tenant_id = (SELECT app_tenant_id()));
CREATE POLICY user_sectors_isolation ON user_sectors USING (tenant_id = (SELECT app_tenant_id()));

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts FORCE ROW LEVEL SECURITY;
CREATE POLICY contacts_isolation ON contacts
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

ALTER TABLE demands ENABLE ROW LEVEL SECURITY;
ALTER TABLE demands FORCE ROW LEVEL SECURITY;
CREATE POLICY demands_isolation ON demands
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

ALTER TABLE demand_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE demand_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY demand_messages_isolation ON demand_messages
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

ALTER TABLE subtasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE subtasks FORCE ROW LEVEL SECURITY;
CREATE POLICY subtasks_isolation ON subtasks
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

-- Login: unica leitura de usuarios fora do contexto de tenant.
CREATE FUNCTION auth_user(p_tenant_slug text, p_email text)
    RETURNS TABLE (user_id uuid, tenant_id uuid, password_hash text, role text, name text)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
        SELECT u.id, u.tenant_id, u.password_hash, u.role, u.name
        FROM users u JOIN tenants t ON t.id = u.tenant_id
        WHERE t.slug = p_tenant_slug AND lower(u.email) = lower(p_email) AND u.active
    $$;

REVOKE ALL ON FUNCTION auth_user(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_user(text, text) TO demanda_app;
