# Changelog
## v0.2.0 - 2026-10-29 development checkpoint
Collected runtime SELECTs in sql/dashboard/ and added a query catalog mapping all tiles, filters and employee views to the shared snapshot. Removed inline SQL from the provider. Saved today's Flask dashboard, live-data provider, shared caching, location/unit hierarchy, name fallback, employee popups, offline tests and project records in a local Git checkpoint. Local credentials/config excluded; no remote push or SQL execution for this update.

## Location/unit filters and employee drill-down - 2026-10-29
Set bold ATTENDANCE OVERVIEW heading and removed intro. Location now follows confirmed device-unit mapping; Unit choices depend on Location. Deduplicated machines and multi-location records. Added cached employee detail rows with EmployeeID and Name/PName fallback, search and incremental display. Read-only live verification ~0.088 seconds; 16 offline checks pass. No database modifications.

## Compact tiles and detail dialogs - 2026-10-29
Replaced the large overview table with compact metric and unit/department tiles. Every tile opens cached summary details in a modal with close/Escape/backdrop dismissal. Preserved filter scope, stale/sample labels, unassigned groups and all-units unmapped counts. Added responsive styling and a local JavaScript asset; no new queries or database changes. 14 offline tests pass; browser QA remains pending.

## Live data activated - 2026-10-29
Enabled live SELECT provider/shared cache in local configuration at user's request. Resolved certificate validation failure using local development trust with encryption retained. Verified 1003 registered, 872 mapped punched and 2 unmapped IDs in about 0.10 seconds. 14 offline checks pass. No database objects/data/settings changed. Restart required for the existing server.

## First attendance dashboard integration - 2026-10-29
Added opt-in SQL SELECT provider, parameterized grouped attendance query and single-process shared cache with refresh locking, failure backoff, stale/error states and date rollover protection. NULL assignments remain visible; filters reuse cached counts. Added Waitress launcher and setup instructions. 14 offline checks pass with mocked SQL; no live SQL executed, DB changes or visual browser verification.

## Local configuration - 2026-10-29
Added ignored config.ini, shareable config.example.ini and INI loader/ODBC string preparation. App startup settings now load from INI. Database connection and cache remain disabled/unimplemented. User permits sa during development, with read-only account before deployment; prohibits object creation and data modification. Six checks pass; no DB connection or SQL execution.

## User-supplied attendance results - 2026-10-29
Recorded SSMS preflight and counts in docs/ATTENDANCE_TEST_RESULTS.md; updated next step to collect IO/TIME Messages and actual execution plans. Performance remains unassessed. No assistant SQL execution or database changes.

## Local attendance prototype - 2026-10-29
Added a Flask sample-data dashboard with unit/department filters, registered/punched/no-punch counts, zero-punch groups and separate unmapped-ID coverage. Added responsive styling, run instructions and route/filter checks. No database connector, SQL execution, settings change or deployment. Live integration and shared-cache decisions await performance results.

## Read-only performance test prepared - 2026-10-29
Added sql/020_attendance_dashboard_readonly_performance.sql: version/isolation preflight, today's distinct punched IDs, unit/department punched and roster headcounts, IO/TIME and actual-plan instructions. Updated next step; no SQL executed or database settings changed.

## Decision update - 2026-10-29
Paused attendance-copy table creation and synchronization. Direct read-only attendance queries with shared application caching will be evaluated first, superseding the MISC-only read requirement. New tables/fields require demonstrated necessity; production performance measurements must guide the decision. Updated project state, README and conversation summary. No SQL executed or database settings changed; existing SQL remains reference only. Refreshed record checksums.

## v0.1.0 — 2026-10-29
Created development checkpoint: decisions, source schema, device map, SQL already discussed, status and next steps.
No working dashboard or sync engine yet. SQL is not validated on live SQL Server and no deployment is claimed.
