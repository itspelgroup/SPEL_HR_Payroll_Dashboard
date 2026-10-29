USE SPEL_ATTENDENCE;
SET NOCOUNT ON;
SELECT s.name AS SchemaName,t.name AS TableName,SUM(p.rows) AS ApproxRowCount
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.partitions p ON p.object_id=t.object_id
WHERE t.name IN ('ZK_CHECKINOUT','zkk_Employees','zkk_Devices','zkk_EmployeeDevices')
AND p.index_id IN (0,1) GROUP BY s.name,t.name ORDER BY t.name;
SELECT t.name AS TableName,c.column_id,c.name AS ColumnName,ty.name AS DataType,
c.max_length,c.precision,c.scale,c.is_nullable,c.is_identity,dc.definition AS DefaultValue
FROM sys.tables t JOIN sys.columns c ON c.object_id=t.object_id
JOIN sys.types ty ON ty.user_type_id=c.user_type_id
LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id
WHERE t.name IN ('ZK_CHECKINOUT','zkk_Employees','zkk_Devices','zkk_EmployeeDevices')
ORDER BY t.name,c.column_id;
SELECT t.name AS TableName,i.name AS IndexName,i.type_desc,i.is_primary_key,i.is_unique,
c.name AS ColumnName,ic.key_ordinal,ic.is_included_column,i.filter_definition
FROM sys.tables t JOIN sys.indexes i ON i.object_id=t.object_id
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE t.name IN ('ZK_CHECKINOUT','zkk_Employees','zkk_Devices','zkk_EmployeeDevices')
ORDER BY t.name,i.name,ic.index_column_id;
SELECT DeviceCode,Name,Location,Unit,Active FROM dbo.zkk_Devices ORDER BY DeviceCode;
SELECT TOP (20) ID,CHECKTIME,CHECKTYPE,SENSORID,InsertedAt FROM dbo.ZK_CHECKINOUT ORDER BY ID DESC;
