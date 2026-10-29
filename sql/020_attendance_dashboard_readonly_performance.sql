/* Prepared only: do not execute yet. No objects or database settings are changed.
   Later, in SSMS with a SELECT-only login:
   1. Run section A alone. Review version, isolation and server clock first.
   2. Confirm CHECKTIME uses Pakistan local time and the date below is appropriate.
   3. Enable Query > Include Actual Execution Plan (Ctrl+M), then run section B.
      Actual plans require execution and SHOWPLAN permission; do not grant here.
   4. Save Results, Messages (IO/CPU/elapsed time), and each plan via
      right-click > Save Execution Plan As (.sqlplan).
   5. If acceptable, repeat B twice serially for warm-cache comparison. Record
      date, time, load and run number. Never clear server caches for this test.
   Inspect reads, seeks/scans, lookups, spills, estimated vs actual rows and
   conversion warnings. Existing indexes only; no index hints or new indexes.
   These are individual query baselines, not a concurrent-load test.
   Reference: https://github.com/MicrosoftDocs/SupportArticles-docs/blob/main/support/sql/includes/performance/collect-cpu-time-elapsed-time-logical-reads.md
*/

-- A. Metadata preflight only. Stop and review before running B.
USE SPEL_ATTENDENCE;
GO
SELECT @@VERSION AS FullVersion,
       SERVERPROPERTY('ProductVersion') AS ProductVersion,
       SERVERPROPERTY('Edition') AS Edition,
       GETDATE() AS ServerLocalNow,
       GETUTCDATE() AS ServerUtcNow;

SELECT name AS DatabaseName, compatibility_level,
       is_read_committed_snapshot_on, snapshot_isolation_state_desc
FROM sys.databases
WHERE database_id = DB_ID();

SELECT session_id, transaction_isolation_level,
       CASE transaction_isolation_level
           WHEN 0 THEN 'Unspecified' WHEN 1 THEN 'Read uncommitted'
           WHEN 2 THEN 'Read committed' WHEN 3 THEN 'Repeatable read'
           WHEN 4 THEN 'Serializable' WHEN 5 THEN 'Snapshot'
       END AS SessionIsolation, open_transaction_count
FROM sys.dm_exec_sessions
WHERE session_id = @@SPID;
GO

-- B. Run separately after reviewing A; no isolation changes or transactions.
USE SPEL_ATTENDENCE;
GO
-- Refuse dirty-read sessions and pre-existing explicit/implicit transactions.
IF NOT EXISTS (SELECT 1 FROM sys.dm_exec_sessions
               WHERE session_id = @@SPID AND transaction_isolation_level = 2)
   OR @@TRANCOUNT <> 0 OR (2 & @@OPTIONS) = 2
BEGIN
    RAISERROR('Use a fresh read-committed session without an open or implicit transaction; review preflight first.', 16, 1);
    RETURN;
END;

-- Uses server-local calendar day, not a rolling 24 hours or payroll shift day.
-- If server clock differs from CHECKTIME convention, supply the correct date.
DECLARE @Today date = CONVERT(date, GETDATE());
DECLARE @Start datetime = CONVERT(datetime, @Today);
DECLARE @End datetime = DATEADD(day, 1, @Start);
SELECT @Start AS InclusiveStart, @End AS ExclusiveEnd;

SET STATISTICS IO ON;
SET STATISTICS TIME ON;

PRINT 'Q1: Distinct biometric IDs punched today (includes unmapped IDs)';
-- Sargable CHECKTIME range can use existing CHECKTIME index.
-- Keep functions off indexed columns. Optimizer chooses actual access path.
SELECT COUNT_BIG(DISTINCT p.USERID) AS DistinctPunchedIdsToday
FROM dbo.ZK_CHECKINOUT AS p
WHERE p.CHECKTIME >= @Start AND p.CHECKTIME < @End;

PRINT 'Q2: Today punched headcounts by employee unit and department';
-- Deduplicate before joining so multiple punches cannot multiply headcounts.
-- USERID is nvarchar(50), EmployeeID varchar(50); convert the small employee
-- side explicitly, retaining the indexed punch USERID without conversion.
-- Review actual plan for conversion/cardinality effects; do not change fields.
;WITH TodayIds AS
(
    SELECT DISTINCT p.USERID
    FROM dbo.ZK_CHECKINOUT AS p
    WHERE p.CHECKTIME >= @Start AND p.CHECKTIME < @End
)
SELECT CASE WHEN e.EmployeeID IS NULL THEN 'Unmapped' ELSE 'Mapped' END AS MappingStatus,
       e.Unit AS EmployeeUnit, e.Department,
       COUNT_BIG(*) AS PunchedHeadcountToday
FROM TodayIds AS p
LEFT JOIN dbo.zkk_Employees AS e
    ON p.USERID = CONVERT(nvarchar(50), e.EmployeeID)
GROUP BY CASE WHEN e.EmployeeID IS NULL THEN 'Unmapped' ELSE 'Mapped' END,
         e.Unit, e.Department
ORDER BY MappingStatus, EmployeeUnit, Department;

PRINT 'Q3: Registered biometric roster headcounts by unit and department';
-- Separate denominator: includes all registered IDs, regardless of punch.
-- Active is device status, so no employment-status filter is inferred.
SELECT e.Unit AS EmployeeUnit, e.Department,
       COUNT_BIG(*) AS RegisteredBiometricHeadcount
FROM dbo.zkk_Employees AS e
GROUP BY e.Unit, e.Department
ORDER BY EmployeeUnit, Department;

SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;
-- If canceled or failed before cleanup, turn both statistics options OFF or
-- close this dedicated session. SET STATISTICS affects this session only.
-- Q1 and the sum of Q2 can differ if punches change between statements.
-- Counts describe recorded IDs, not confirmed presence or employment/absence.
-- Shared application caching remains the intended next design evaluation;
-- choose refresh interval only after reviewing these measurements and load.
