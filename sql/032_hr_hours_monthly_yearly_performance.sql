/* Manual read-only SSMS test. Enable actual plan (Ctrl+M), save Messages and
   .sqlplan. No database objects/data/settings changed. Do not clear caches.
   This is a compact totals comparison; for exact runtime dimensions use
   sql/dashboard/hr_hours_periods.sql, replacing its five ODBC ? markers with
   50001,@Start,@End,@Start,@End. No automatic execution of this file/folder.
*/
USE SBO_AI;
GO
DECLARE @Start datetime='20230701';
DECLARE @End datetime=DATEADD(day,1,CONVERT(date,GETDATE()));
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
;WITH Combined AS
(
    SELECT DocDate,NetWorkingHours_D,OvertimeAdjustment_D
    FROM dbo.HR_MIS WHERE DocDate>=@Start AND DocDate<@End
    UNION ALL
    SELECT DocDate,NetWorkingHours_D,OvertimeAdjustment_D
    FROM dbo.HR_MIS_C WHERE DocDate>=@Start AND DocDate<@End
)
SELECT CASE WHEN MONTH(DocDate)>=7 THEN YEAR(DocDate) ELSE YEAR(DocDate)-1 END AS FiscalStartYear,
       (MONTH(DocDate)+5)%12+1 AS FiscalMonthOrder,
       YEAR(DocDate) AS CalendarYear,MONTH(DocDate) AS CalendarMonth,COUNT_BIG(*) AS SourceRecords,
       SUM(CONVERT(decimal(28,8),NetWorkingHours_D)) AS NetHours,
       SUM(CONVERT(decimal(28,8),OvertimeAdjustment_D)) AS OvertimeHours,
       SUM(CONVERT(decimal(28,8),NetWorkingHours_D))+
       SUM(CONVERT(decimal(28,8),OvertimeAdjustment_D)) AS TotalHours,
       MIN(DocDate) AS FirstRecord,MAX(DocDate) AS LastRecord
FROM Combined GROUP BY YEAR(DocDate),MONTH(DocDate)
ORDER BY FiscalStartYear,FiscalMonthOrder;
SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;
-- Total = net working hours (excludes overtime) + overtime hours.
-- Inspect recorded date coverage before comparing partial months or years.
-- Fiscal year runs July to June; FiscalStartYear 2025 means FY 2025/26.
