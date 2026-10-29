-- Previously requested; results not received. No mutations.
USE SBO_PAYROLL;
SELECT COUNT(*) AS TotalEmployees,
SUM(CASE WHEN UpdateDate IS NULL THEN 1 ELSE 0 END) AS MissingUpdateDate,
MAX(CreateDate) AS LatestCreateDate,MAX(UpdateDate) AS LatestUpdateDate FROM dbo.MstEmployee;
SELECT TOP (10) ID AS PAYROLLID,CreateDate,UpdateDate FROM dbo.MstEmployee ORDER BY UpdateDate DESC;
SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.GetDateDifference')) AS FunctionDefinition;
SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.MstEmployee_SBO')) AS ViewDefinition;
