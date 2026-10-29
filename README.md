# SPEL HR & Payroll Dashboard
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
