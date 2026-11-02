-- Parameter: earliest punch time to examine.
-- Preserve every event at the latest timestamp so conflicting IN/OUT ties
-- can be marked unresolved instead of manufacturing a presence state.
WITH Latest AS (
    SELECT USERID, MAX(CHECKTIME) AS LastTime
    FROM dbo.ZK_CHECKINOUT
    WHERE CHECKTIME >= ?
    GROUP BY USERID
)
SELECT p.USERID, p.CHECKTIME, p.SENSORID
FROM dbo.ZK_CHECKINOUT AS p
JOIN Latest AS latest ON latest.USERID = p.USERID AND latest.LastTime = p.CHECKTIME;
