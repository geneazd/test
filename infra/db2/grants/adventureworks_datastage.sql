-- infra/db2/grants/adventureworks_datastage.sql
--
-- Purpose:
-- Restore the least-privilege IBM Db2 Warehouse access required by the
-- AdventureWorks IBM DataStage ingestion service account.
--
-- Target database: IBM_STACK_1_BRONZE
-- Target schema:   ADVENTUREWORKS
-- Service account: SVC_DATASTAGE_ADVENTUREWORKS
--
-- Notes:
-- - Run using a Db2 administrator or security owner account.
-- - This script uses dynamic SQL for existing table grants.
-- - Future table grants should be applied as part of table provisioning or
--   through your Db2 security automation process.

CONNECT TO IBM_STACK_1_BRONZE;

GRANT CONNECT ON DATABASE
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

GRANT CREATEIN, ALTERIN ON SCHEMA ADVENTUREWORKS
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

-- Grant DML privileges on known ingestion target tables.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ADVENTUREWORKS.ORDERS
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ADVENTUREWORKS.CUSTOMERS
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ADVENTUREWORKS.SALES
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

-- Optional: grant DML privileges on all current tables in the schema.
-- Uncomment and run with a Db2 SQL PL terminator if your environment allows it.
--
-- --#SET TERMINATOR @
-- BEGIN
--   FOR table_cursor AS
--     SELECT tabschema, tabname
--     FROM syscat.tables
--     WHERE tabschema = 'ADVENTUREWORKS'
--       AND type = 'T'
--   DO
--     EXECUTE IMMEDIATE
--       'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "'
--       || table_cursor.tabschema || '"."'
--       || table_cursor.tabname || '" TO USER SVC_DATASTAGE_ADVENTUREWORKS';
--   END FOR;
-- END@
-- --#SET TERMINATOR ;
