-- SBO_AI is on the same SQL Server as the configured attendance connection.
-- Cross-database SELECTs keep attendance's default database/config unchanged.
SELECT HAS_DBACCESS(N'SBO_AI'), transaction_isolation_level
FROM sys.dm_exec_sessions WHERE session_id = @@SPID;
