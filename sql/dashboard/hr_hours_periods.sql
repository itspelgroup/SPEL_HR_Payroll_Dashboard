-- Monthly aggregation for monthly/yearly comparisons, combining both sources.
-- Parameters: max_groups+1, inclusive start, exclusive end, start, end.
-- No employee-day transfer or new database objects. Signed hours retained.
SELECT TOP (?) DATEFROMPARTS(YEAR(DocDate), MONTH(DocDate), 1) AS MonthStart,
       Unit, Department, WorkerType, DirectWorker, COUNT_BIG(*) AS RecordCount,
       SUM(CONVERT(decimal(28,8), NetWorkingHours_D)) AS NetHours,
       SUM(CONVERT(decimal(28,8), OvertimeAdjustment_D)) AS OvertimeHours,
       MIN(DocDate) AS FirstRecord, MAX(DocDate) AS LastRecord
FROM (
    SELECT Unit, Department, WorkerType, DirectWorker, DocDate,
           NetWorkingHours_D, OvertimeAdjustment_D
    FROM SBO_AI.dbo.HR_MIS WHERE DocDate >= ? AND DocDate < ?
    UNION ALL
    SELECT Unit, Department, WorkerType, DirectWorker, DocDate,
           NetWorkingHours_D, OvertimeAdjustment_D
    FROM SBO_AI.dbo.HR_MIS_C WHERE DocDate >= ? AND DocDate < ?
) AS Combined
GROUP BY DATEFROMPARTS(YEAR(DocDate), MONTH(DocDate), 1),
         Unit, Department, WorkerType, DirectWorker;
