/* Manual SSMS test only. Run A first. Enable Include Actual Execution Plan
   (Ctrl+M) before B; save Results, Messages (IO/TIME) and .sqlplan files.
   No database objects/data/settings changed. Never clear server caches.
*/
USE SBO_AI;
GO
-- A. Metadata preflight.
SELECT @@VERSION AS SqlVersion, GETDATE() AS ServerLocalNow;
SELECT name, compatibility_level, is_read_committed_snapshot_on,
       snapshot_isolation_state_desc FROM sys.databases WHERE database_id=DB_ID();
SELECT transaction_isolation_level FROM sys.dm_exec_sessions WHERE session_id=@@SPID;
SELECT t.name AS TableName, i.name AS IndexName, i.type_desc
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.indexes i ON i.object_id=t.object_id
WHERE s.name=N'dbo' AND t.name IN (N'HR_MIS',N'HR_MIS_C');
GO
-- B. Last seven calendar days; exclusive end. Edit dates for historical tests.
DECLARE @End datetime=DATEADD(day,1,CONVERT(date,GETDATE()));
DECLARE @Start datetime=DATEADD(day,-7,@End);
SELECT @Start AS InclusiveStart,@End AS ExclusiveEnd;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
;WITH Combined AS
(
    SELECT N'HR_MIS' AS SourceTable, SPELID, DocDate,
           NetWorkingHours_D, OvertimeAdjustment_D
    FROM dbo.HR_MIS WHERE DocDate>=@Start AND DocDate<@End
    UNION ALL
    SELECT N'HR_MIS_C', SPELID, DocDate, NetWorkingHours_D, OvertimeAdjustment_D
    FROM dbo.HR_MIS_C WHERE DocDate>=@Start AND DocDate<@End
)
SELECT SourceTable,COUNT_BIG(*) AS SourceRows,
       COUNT(DISTINCT NULLIF(LTRIM(RTRIM(SPELID)),N'')) AS DistinctEmployeeIds,
       MIN(DocDate) AS FirstDate,MAX(DocDate) AS LastDate,
       SUM(NetWorkingHours_D) AS NetWorkingHours,
       SUM(OvertimeAdjustment_D) AS OvertimeAdjustmentHours
FROM Combined GROUP BY SourceTable;
SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;
-- This aggregate does not measure UI rendering/row transfer.
-- For exact runtime retrieval, copy sql/dashboard/hr_hours_records.sql and replace
-- its five ODBC ? markers with 50001,@Start,@End,@Start,@End respectively.
-- More than max_rows must not be presented as full totals. No automatic execution.
