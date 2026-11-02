-- Read-only filter catalog, shared by all users through the snapshot cache.
-- Include devices even when their units have no employees in the roster.
SELECT DISTINCT Location, Unit
FROM dbo.zkk_Devices;
