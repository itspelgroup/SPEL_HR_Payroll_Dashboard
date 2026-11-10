-- Parameters: Pakistan-local lookback start and current time.
-- Classify the bounded punch set once, then use window aggregates for the
-- latest event and last IN/OUT timestamps. Preserve latest-event ties.
;WITH DeviceTokens AS
(
    SELECT DeviceCode,
           ' ' + REPLACE(REPLACE(UPPER(ISNULL(Name, '')), '-', ' '), '_', ' ') + ' ' AS Tokens
    FROM dbo.zkk_Devices
),
DeviceDirections AS
(
    SELECT DeviceCode,
           CASE
               WHEN Tokens LIKE '% IN %' AND Tokens NOT LIKE '% OUT %' THEN 'IN'
               WHEN Tokens LIKE '% OUT %' AND Tokens NOT LIKE '% IN %' THEN 'OUT'
               ELSE NULL
           END AS Direction
    FROM DeviceTokens
),
ClassifiedPunches AS
(
    SELECT p.USERID, p.CHECKTIME, p.SENSORID, d.Direction
    FROM dbo.ZK_CHECKINOUT AS p
    LEFT JOIN DeviceDirections AS d
      ON d.DeviceCode = CONVERT(varchar(50), p.SENSORID)
    WHERE p.CHECKTIME >= ?
      AND p.CHECKTIME <= ?
),
PunchWindow AS
(
    SELECT USERID,
           CHECKTIME,
           SENSORID,
           MAX(CHECKTIME) OVER (PARTITION BY USERID) AS LastEvent,
           MAX(CASE WHEN Direction = 'IN' THEN CHECKTIME END)
               OVER (PARTITION BY USERID) AS LastInPunch,
           MAX(CASE WHEN Direction = 'OUT' THEN CHECKTIME END)
               OVER (PARTITION BY USERID) AS LastOutPunch
    FROM ClassifiedPunches
)
SELECT USERID, CHECKTIME, SENSORID, LastInPunch, LastOutPunch
FROM PunchWindow
WHERE CHECKTIME = LastEvent;
