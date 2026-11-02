-- Read-only device overview. Cached once per refresh, never per tile.
-- Activity follows CHECKTIME; latest punch receipt is retained separately.
SELECT d.DeviceCode, d.Name, d.Location, CAST(NULL AS nvarchar(20)), d.Active,
       latest.CHECKTIME AS LastPunch, latest.InsertedAt AS LastReceived
FROM dbo.zkk_Devices AS d
OUTER APPLY (
    SELECT TOP (1) p.CHECKTIME, p.InsertedAt
    FROM dbo.ZK_CHECKINOUT AS p
    WHERE p.SENSORID = d.DeviceCode
    ORDER BY p.CHECKTIME DESC, p.ID DESC
) AS latest;
