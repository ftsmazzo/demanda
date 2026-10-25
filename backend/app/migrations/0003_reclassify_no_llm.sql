-- Uma classificacao feita so com regras (reason = 'no_llm') nao e definitiva: quando houver IA,
-- a mensagem pode ganhar uma segunda linha. As demais continuam unicas por (mensagem, versao).
ALTER TABLE message_classifications
    DROP CONSTRAINT message_classifications_message_id_rules_version_key;

CREATE UNIQUE INDEX message_classifications_final_idx
    ON message_classifications (message_id, rules_version)
    WHERE reason IS DISTINCT FROM 'no_llm';
