-- Application SELECT template. Parameters: day start, day end (ODBC markers).
-- Review plan/IO/TIME before live use. No hints, objects or data modification.
;WITH TodayIds AS
(
    SELECT DISTINCT USERID FROM dbo.ZK_CHECKINOUT
    WHERE CHECKTIME >= ? AND CHECKTIME < ?
)
SELECT e.Unit, e.Department,
       COUNT_BIG(e.EmployeeID) AS RegisteredCount,
       COUNT_BIG(p.USERID) AS PunchedCount,
       CASE WHEN e.EmployeeID IS NULL THEN 0 ELSE 1 END AS IsMapped
FROM dbo.zkk_Employees AS e
FULL OUTER JOIN TodayIds AS p
    ON p.USERID = CONVERT(nvarchar(50), e.EmployeeID)
GROUP BY e.Unit, e.Department,
         CASE WHEN e.EmployeeID IS NULL THEN 0 ELSE 1 END;
