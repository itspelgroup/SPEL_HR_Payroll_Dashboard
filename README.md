# SPEL HR & Payroll Dashboard

Multi-user access (2026-11-07): local authentication is now enabled. Restart `python serve.py`, sign in with the existing administrator, and open **Settings** to create users with multiple allowed tabs and locations. Private `users.ini` holds the accounts; new/reset passwords are readable as requested, with optional hash storage. HR access requires explicit location-to-HR-unit mappings. Use one central server for all locations/users. See [account setup and deployment](docs/DASHBOARD_ACCOUNTS.md). No production SQL was executed for this increment. Older authentication-deferred notes below are superseded.

For a Windows LAN sample deployment, run `start-lan.bat` on the server and, from elevated PowerShell, optionally run `.\allow-lan-firewall.ps1`; clients open `http://SERVER-IP:5000`. Before exposing real data, enable authentication and configure a read-only SQL account. See [LAN deployment](docs/DEPLOY_LAN.md) for the full setup and HTTPS guidance.

Current HR Hours view is simplified: Monthly pairs the current FY with the previous FY month by month (July-June); Yearly shows every available FY plus current YTD. Each bar shows working, overtime and total values. Optional filters are collapsed; only three YTD tiles remain. See docs/HR_HOURS.md and restart python serve.py / Ctrl+F5 after updating.

HR graphs now compare July–June fiscal years and months. Select first/last FY; each period has one stacked net-plus-overtime bar with total marked above it, a legend and named axes. Current FY is partial and future months are Upcoming. Restart python serve.py and Ctrl+F5 for the updated graph.

HR Hours now opens Monthly analysis by default, with Yearly comparisons and Employee/Daily detail tabs. Graphs compare net, overtime and total hours; total = net + overtime. Source filtering is removed. Long periods use compact SQL aggregates with shared caching. Restart python serve.py and Ctrl+F5 after updating. Details: docs/HR_HOURS.md.

HR Hours tab (2026-11-07): `/hr-hours` adds bounded SBO_AI HR_MIS/HR_MIS_C net-hours and overtime analysis, employee/unit/department/worker/date insights and cached detail popups. Restart `python serve.py` and hard-refresh to see the fourth tab. See docs/HR_HOURS.md for query evaluation, performance and validation notes.

HR/Payroll source decision (2026-11-07): build upcoming HR and Payroll dashboards from SBO_AI. Existing attendance dashboards continue reading SPEL_ATTENDENCE. First inventory SBO_AI tables/views and relationships using read-only metadata queries; its schema is not yet confirmed. See docs/PROJECT_STATE.md.

Latest checkpoint v0.3.0 (2026-11-02): three tabs?Machines, Attendance Alerts and Employees. Staff screens are tile-only with shared filtered popups. Designation and authentication are deferred. See docs/PROJECT_STATE.md for current status; older setup notes below are historical. 49 Python tests and 8 JavaScript checks pass. No deployment or live-query verification is claimed.

Current decision (2026-10-31): authentication is deferred. No sign-in is required by default, including live mode. Location is the baseline scope for all dashboard screens and filters. Retained account support is inactive unless explicitly enabled in local security settings; location selection is currently a filter, not an access restriction.

Machine-only black layout and location accounts: see docs/DASHBOARD_ACCOUNTS.md. Live mode now requires sign-in by default; create an administrator using python -m dashboard.users --username admin --admin before opening the app. Machine popups show the last received user's ID, PName, PhysicalLocation and timestamps. UI, login and query verification are pending locally.

Latest development (2026-10-31): the home page is Machine Overview; employee attendance is at /attendance. Machine activity follows the last database receipt (InsertedAt), with Recent <=60 minutes, Delayed <=1440 minutes, and No recent punches thereafter. Disabled and never-received devices are included. Location summaries count devices from zkk_Devices. sql/dashboard/machine_snapshot.sql is a read-only aggregate cached in one process; production query cost and SQL timestamp timezone still require verification. No connectivity probing is performed. Run python serve.py and open http://127.0.0.1:5000. Offline tests for these changes have not been executed in the assistant environment.

Checkpoint v0.2.0 — 2026-10-29 (Asia/Karachi)

Start with docs/PROJECT_STATE.md. The first attendance dashboard supports sample mode and an opt-in SQL SELECT provider; live integration is not yet verified and no production deployment exists.
The existing ZKTeco Workforce Manager remains separate and unchanged.

Local configuration is now live: restart python serve.py to load it. The SELECT provider was verified against existing attendance tables; no database changes occurred. Shareable config.example.ini remains demo by default. Full SQL performance-plan/load review remains pending. Earlier no-execution notes describe previous checkpoints.

Run locally: `python -m pip install -r requirements.txt`, then `python serve.py`. Open http://127.0.0.1:5000 and stop with Ctrl+C. Defaults use labelled fictional records. Unit/department filters update attendance counts. See docs/DASHBOARD_SETUP.md for SQL activation after performance review. No authentication is implemented; keep the server local.

Verify with `python -m unittest discover -s tests -v`.

Settings: edit local `config.ini` (excluded from Git); `config.example.ini` is the shareable template. Set the SQL password locally or use SPEL_SQL_PASSWORD. An optional full ODBC connection_string overrides individual database fields; SPEL_SQL_CONNECTION_STRING overrides both. Do not share filled-in configuration or include it in checkpoint ZIPs. App settings, database timeouts and cache TTL are implemented. Live mode requires data_mode=live, database enabled=true and cache enabled=true. Leave sample mode enabled until performance review. A single Waitress process shares one cache across users/threads. No SQL is run merely by loading the configuration or creating the app.

Development may use sa as requested; switch to a SELECT-only account before deployment. ReadOnly connection intent does not restrict sa permissions. No application feature may create objects or modify existing data; database settings remain unchanged.

Contents: requirements/decisions, conversation summary, source schema inventory, device mapping, initial destination SQL, validation queries, next steps and release notes.

Current working folder: C:\Projects\SPEL_HR_Payroll_Dashboard
Keep checkpoints outside the live application directory. Never execute all SQL files automatically.
Authorized SELECT-only live verification has succeeded; no database objects, settings or existing data were changed. The earlier CREATE TABLE proposal remains paused.

Latest decision (2026-10-29): attendance-copy table creation and synchronization are paused. First evaluate direct, read-only queries against existing attendance tables with shared application caching. Create tables/fields only when necessary; prioritize production performance and measure before deciding. Next: prepare the query/cache evaluation and measurement plan. Do not execute SQL or change database settings yet. Existing SQL files are retained as reference only.

Future continuity: resume from docs/PROJECT_STATE.md. This folder now has a local Git repository for development checkpoints; no remote is configured and no push or automatic backup is provided. config.ini and secrets remain excluded. Runtime queries and their tile/view catalog are in sql/dashboard/README.md. Update records and checksums with each checkpoint.

The conversation record is a curated summary, not a verbatim chat export. Original attendance project remains available as the separately uploaded ZKTeco_WorkForce_Manager.rar; it is not duplicated here because it contains local settings/secrets/logs. No production credentials are included.
