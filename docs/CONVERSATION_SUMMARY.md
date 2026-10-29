# Conversation decisions — curated, not verbatim
1. User requested independent SPEL HR/payroll/HCM dashboard extending ideas from uploaded attendance app.
2. Inspection found Python Flask, SQL Server/pyodbc, dashboard services and schema-changing DB initialization; do not reuse that DB initialization in read-only dashboard.
3. Proposed separate internal-server application and private Git versions. Neither deployment nor Git established.
4. User provided employee view and requested no production tables/indexes unless mandatory; needs live and historical analysis.
5. Discussed SELECT INTO MISC.dbo.DB_MstEmployee (one-time create, not recurring sync). Creation not confirmed.
6. View definition revealed master UpdateDate and related dependencies; performance 9 seconds reported. Function definition/plan not provided.
7. User described raw machine -> attendance -> policy-processed payroll -> monthly register -> accounts workflow and chose attendance first, dashboard data in MISC.
8. User supplied four-table schema/indexes/counts: captured in reference/attendance_schema.json. Confirmed mostly inserts, rare corrections/deletes, never reset IDs; corrections within 30 days.
9. Device list confirms explicit IN/OUT naming, raw CHECKTYPE unreliable. Sample latest ID 611910 at 2026-10-29 10:09:54, inserted 10:10:02.080; 20 records descending ID were shared. Full sample not reproduced; source facts and mapping preserved.
10. Assistant supplied empty DB_AttendancePunch create script (included). Awaiting user confirmation of execution.
11. User requests saving project/chat/code/materials for future development. This checkpoint records current context and SQL; no claim of automatic transcript capture or access to user's PC.
12. Latest decision (2026-10-29): pause the attendance-copy table and synchronization plan. First evaluate direct, read-only queries against existing attendance tables with shared application caching, superseding the earlier MISC-only read requirement. Create tables/fields only when necessary. Production performance takes priority; measure before deciding. Next prepare the evaluation and measurement plan, without executing SQL or changing database settings yet. The earlier CREATE TABLE and copy/sync next steps are superseded.
13. User supplied successful SSMS count/preflight results (docs/ATTENDANCE_TEST_RESULTS.md), then permitted sa for development and requested local config.ini. No database objects or existing data may be changed. Read-only account required before deployment.
14. First attendance dashboard now supports labelled sample data and opt-in SQL SELECTs, unit/department filters, zero-punch/unassigned groups, global unmapped coverage and explicit stale/unavailable states. One Waitress process shares the in-memory cache across users/threads. No live SQL executed by assistant; performance results and measurement of the consolidated query remain pending. Live activation and setup are documented in docs/DASHBOARD_SETUP.md. Local connection settings were preserved.

16. User requested separate dashboard query storage and today's commit. Runtime SELECTs moved into sql/dashboard/ with a tile/view query catalog; all tiles still share one cached employee snapshot. Local Git repository initialized, no remote push. Credentials/local config remain excluded.
