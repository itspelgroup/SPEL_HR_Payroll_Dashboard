# Original application reference
Filename: ZKTeco_WorkForce_Manager.rar
Previously uploaded file identity: libfile_95485fcbfc2481919c24679e36ef6841
Original reference only; not a dependency to execute.
Stack inspected: Flask 3.0.3, Werkzeug 3.0.3, waitress 3.0.0, pyodbc 5.3.0, SQL Server ODBC 17, Python Windows launchers.
Relevant modules: modules/dashboard/service.py, modules/attendance/service.py, modules/employees/service.py, core/db.py, core/auth.py, core/presence.py, core/zk_client.py.
Do not import old core/db.py unchanged: it runs migrations on first connection. Employee edit/repair logic can write to records and devices. Old project is operational device software, new project is reporting.
Original archive/config/secrets/logs are intentionally not copied into this portable checkpoint. Keep original separately and protect access.
