-- At most 15 latest punch events per machine, ordered deterministically.
-- Employee unit belongs to the employee, not to the machine.
SELECT d.DeviceCode, p.ID, p.USERID, p.CHECKTIME, p.InsertedAt,
       e.PName, e.Unit, e.PhysicalLocation
FROM dbo.zkk_Devices AS d
CROSS APPLY (
    SELECT TOP (?) ID, USERID, CHECKTIME, InsertedAt
    FROM dbo.ZK_CHECKINOUT AS p
    WHERE p.SENSORID = d.DeviceCode
    ORDER BY CHECKTIME DESC, ID DESC
) AS p
LEFT JOIN dbo.zkk_Employees AS e
    ON CONVERT(nvarchar(50), e.EmployeeID) = p.USERID
ORDER BY d.DeviceCode, p.CHECKTIME DESC, p.ID DESC;
