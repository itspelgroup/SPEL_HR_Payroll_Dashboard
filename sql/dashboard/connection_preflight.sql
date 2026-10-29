-- Read-only connection validation; performed once per snapshot refresh.
-- Requires SPEL_ATTENDENCE and read-committed session isolation (2).
SELECT DB_NAME(), transaction_isolation_level
FROM sys.dm_exec_sessions
WHERE session_id = @@SPID;
