-- Setores por tenant: a lista deixa de ser fixa no codigo e vira dado (cada escritorio tem os seus).
-- triagem e rh-interno sao do sistema (nao podem ser desligados): triagem e o destino quando nada
-- se encaixa e rh-interno tem acesso restrito.
CREATE TABLE sectors (
    tenant_id  uuid NOT NULL REFERENCES tenants (id),
    slug       text NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) <= 40),
    label      text NOT NULL CHECK (length(label) BETWEEN 1 AND 40),
    color      text NOT NULL CHECK (color ~ '^#[0-9a-fA-F]{6}$'),
    system     boolean NOT NULL DEFAULT false,
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, slug)
);

CREATE FUNCTION seed_default_sectors(target uuid) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
    -- created_at escalonado: a ordem da lista e a ordem de criacao
    INSERT INTO sectors (tenant_id, slug, label, color, system, created_at)
    SELECT target, slug, label, color, system, now() + (position * interval '1 millisecond')
    FROM (VALUES (1, 'triagem', 'Triagem', '#7b8a84', true),
                 (2, 'fiscal', 'Fiscal', '#3a6ea5', false),
                 (3, 'contabil', 'Contábil', '#7a8450', false),
                 (4, 'dp', 'Pessoal', '#a8573e', false),
                 (5, 'societario', 'Societário', '#6b4e7a', false),
                 (6, 'financeiro', 'Financeiro', '#c28f2c', false),
                 (7, 'rh-interno', 'RH interno', '#8e3b55', true),
                 (8, 'consultoria', 'Consultoria', '#2f7f86', false)
    ) AS defaults (position, slug, label, color, system)
    ON CONFLICT DO NOTHING
$$;
REVOKE ALL ON FUNCTION seed_default_sectors(uuid) FROM PUBLIC;

CREATE FUNCTION seed_sectors_on_new_tenant() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
BEGIN
    PERFORM seed_default_sectors(NEW.id);
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION seed_sectors_on_new_tenant() FROM PUBLIC;

CREATE TRIGGER tenants_seed_sectors AFTER INSERT ON tenants
    FOR EACH ROW EXECUTE FUNCTION seed_sectors_on_new_tenant();

SELECT seed_default_sectors(id) FROM tenants;

-- sem FORCE (como users): o gatilho e o dono precisam semear sem contexto de tenant.
GRANT SELECT, INSERT, UPDATE ON sectors TO demanda_app;
ALTER TABLE sectors ENABLE ROW LEVEL SECURITY;
CREATE POLICY sectors_isolation ON sectors
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

ALTER TABLE message_classifications DROP CONSTRAINT message_classifications_sector_check;
ALTER TABLE message_classifications ADD CONSTRAINT message_classifications_sector_fk
    FOREIGN KEY (tenant_id, sector) REFERENCES sectors (tenant_id, slug);
ALTER TABLE user_sectors DROP CONSTRAINT user_sectors_sector_check;
ALTER TABLE user_sectors ADD CONSTRAINT user_sectors_sector_fk
    FOREIGN KEY (tenant_id, sector) REFERENCES sectors (tenant_id, slug);
ALTER TABLE demands DROP CONSTRAINT demands_sector_check;
ALTER TABLE demands ADD CONSTRAINT demands_sector_fk
    FOREIGN KEY (tenant_id, sector) REFERENCES sectors (tenant_id, slug);
