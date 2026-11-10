-- Active biometric employee roster. Not a payroll employment-status filter.
SELECT EmployeeID, PName, Unit, Department, PhysicalLocation
FROM dbo.zkk_Employees
WHERE Active = 1;
