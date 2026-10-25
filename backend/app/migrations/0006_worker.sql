-- O processamento em segundo plano precisa saber quais tenants existem, mas o papel de runtime
-- nao enxerga a tabela (RLS). Esta funcao devolve so os ids, no mesmo molde de auth_channel.
CREATE FUNCTION list_tenant_ids()
    RETURNS SETOF uuid
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
        SELECT id FROM tenants ORDER BY created_at, id
    $$;

REVOKE ALL ON FUNCTION list_tenant_ids() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION list_tenant_ids() TO demanda_app;
