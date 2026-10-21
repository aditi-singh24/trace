-- Database-level append-only protection for audit_chain (run once after migrations).
-- The application also blocks ORM updates/deletes, but this holds even for raw SQL.

CREATE OR REPLACE FUNCTION audit_chain_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_chain is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_chain_no_update_delete ON audit_chain;
CREATE TRIGGER audit_chain_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_chain
    FOR EACH ROW EXECUTE FUNCTION audit_chain_block_mutation();

DROP TRIGGER IF EXISTS audit_chain_no_truncate ON audit_chain;
CREATE TRIGGER audit_chain_no_truncate
    BEFORE TRUNCATE ON audit_chain
    FOR EACH STATEMENT EXECUTE FUNCTION audit_chain_block_mutation();

-- Also restrict the application role (replace trace_app with your role name):
-- REVOKE UPDATE, DELETE, TRUNCATE ON audit_chain FROM trace_app;
-- GRANT SELECT, INSERT ON audit_chain TO trace_app;
