-- Biometric roster, not confirmed employment status.
SELECT e.EmployeeID, e.PName, e.Unit, e.Department, e.PhysicalLocation,
       payroll.BranchName
FROM dbo.zkk_Employees AS e
OUTER APPLY
(
    SELECT MAX(BranchName) AS BranchName
    FROM dbo.zkk_Employees_Payroll
    WHERE SPELID = e.EmployeeID
) AS payroll;
