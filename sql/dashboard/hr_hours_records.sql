-- Shared HR Hours snapshot. Parameters: max_rows+1, start, end, start, end.
-- End is exclusive. Never display a partial snapshot if the row cap is exceeded.
-- Retain UNION ALL semantics and source identity; do not deduplicate hours.
SELECT TOP (?) SourceTable, Unit, WorkerType, SPELID, EmpName, Department,
       DocDate, TimeIn, TimeOut, DirectWorker, NetWorkingHours_D,
       OvertimeAdjustment_D, CreateDateAI
FROM (
    SELECT N'HR_MIS' AS SourceTable, Unit, WorkerType, SPELID, EmpName,
           Department, DocDate, TimeIn, TimeOut, DirectWorker,
           NetWorkingHours_D, OvertimeAdjustment_D, CreateDateAI
    FROM SBO_AI.dbo.HR_MIS
    WHERE DocDate >= ? AND DocDate < ?
    UNION ALL
    SELECT N'HR_MIS_C', Unit, WorkerType, SPELID, EmpName,
           Department, DocDate, TimeIn, TimeOut, DirectWorker,
           NetWorkingHours_D, OvertimeAdjustment_D, CreateDateAI
    FROM SBO_AI.dbo.HR_MIS_C
    WHERE DocDate >= ? AND DocDate < ?
) AS Combined;
