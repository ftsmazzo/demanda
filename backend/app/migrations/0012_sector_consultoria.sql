-- Novo setor: consultoria (pareceres, planejamento, diagnosticos). Reescreve as restricoes de
-- setor das tres tabelas que a guardam.
DO $$
DECLARE
    item record;
BEGIN
    FOR item IN
        SELECT conrelid::regclass::text AS tbl, conname
        FROM pg_constraint
        WHERE contype = 'c'
          AND conrelid::regclass::text IN ('message_classifications', 'user_sectors', 'demands')
          AND pg_get_constraintdef(oid) LIKE '%rh-interno%'
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', item.tbl, item.conname);
    END LOOP;
END
$$;

ALTER TABLE message_classifications ADD CONSTRAINT message_classifications_sector_check CHECK (
    sector IN ('triagem', 'fiscal', 'contabil', 'dp', 'societario', 'financeiro', 'rh-interno',
               'consultoria')
);
ALTER TABLE user_sectors ADD CONSTRAINT user_sectors_sector_check CHECK (
    sector IN ('triagem', 'fiscal', 'contabil', 'dp', 'societario', 'financeiro', 'rh-interno',
               'consultoria')
);
ALTER TABLE demands ADD CONSTRAINT demands_sector_check CHECK (
    sector IN ('triagem', 'fiscal', 'contabil', 'dp', 'societario', 'financeiro', 'rh-interno',
               'consultoria')
);
