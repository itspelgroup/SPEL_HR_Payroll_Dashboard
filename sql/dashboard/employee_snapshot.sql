-- Fixed SELECT: employee details and today's distinct punches.
-- Shared source for all attendance tiles, filters and employee detail popups.
-- ODBC parameters: Pakistan-local calendar day start/end.
-- Location follows employee Unit -> device Unit, not punch/enrolment location.
-- Device mapping is deduplicated; application deduplicates multi-location rows.
;WITH TodayIds AS
(
    SELECT DISTINCT USERID FROM dbo.ZK_CHECKINOUT
    WHERE CHECKTIME >= ? AND CHECKTIME < ?
), UnitLocations AS
(
    SELECT DISTINCT Unit, Location FROM dbo.zkk_Devices
    WHERE Unit IS NOT NULL
)
SELECT e.EmployeeID, e.Name, e.PName, e.Unit, e.Department,
       p.USERID AS PunchedId, d.Location
FROM dbo.zkk_Employees AS e
FULL OUTER JOIN TodayIds AS p
    ON p.USERID = CONVERT(nvarchar(50), e.EmployeeID)
LEFT JOIN UnitLocations AS d ON d.Unit = e.Unit;
