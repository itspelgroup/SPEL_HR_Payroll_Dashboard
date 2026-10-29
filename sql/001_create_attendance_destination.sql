-- Proposed in chat; user execution NOT confirmed. Creates MISC object only.
USE MISC;
GO
IF OBJECT_ID(N'dbo.DB_AttendancePunch', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.DB_AttendancePunch
    (
        ID BIGINT NOT NULL,
        USERID NVARCHAR(50) NOT NULL,
        CHECKTIME DATETIME NOT NULL,
        CHECKTYPE NVARCHAR(2) NULL,
        VERIFYCODE INT NULL,
        SENSORID NVARCHAR(50) NULL,
        WorkCode INT NULL,
        sn NVARCHAR(100) NULL,
        DeviceIP NVARCHAR(50) NULL,
        InsertedAt DATETIME NOT NULL,
        CONSTRAINT PK_DB_AttendancePunch PRIMARY KEY CLUSTERED (ID)
    );
    PRINT 'Created MISC.dbo.DB_AttendancePunch.';
END
ELSE
    PRINT 'Table already exists; no changes made.';
GO
-- Existing object schema must be checked before loading. Source ID is NOT destination identity.
