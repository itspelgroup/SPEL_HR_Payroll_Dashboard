# First attendance dashboard

From C:\Projects\SPEL_HR_Payroll_Dashboard:

```powershell
python -m pip install -r requirements.txt
python serve.py
```

Open http://127.0.0.1:5000. Stop with Ctrl+C. Use one server process so all users/threads share the same memory cache. Keep local until authentication and deployment are implemented.

The compact ATTENDANCE OVERVIEW has Location and Unit filters, four metric tiles and unit tiles. Location follows employee Unit matched to zkk_Devices.Unit/Location, as confirmed by the user. Unit options narrow when Location changes. IN/OUT machines do not multiply employee counts; missing unit-location mappings appear as Not assigned. Employees mapped to multiple locations count once globally, but appear in each relevant location filter. Location is an assignment mapping, not proof of where someone punched.

Click a tile (or focus it and press Enter) for employee rows: EmployeeID, name, location, unit, department and punch status. Name falls back to PName when blank/NULL, numeric/ID-only or an obvious placeholder such as User123, Employee123, Unknown or N/A; neither valid shows Name unavailable. This heuristic does not change source data. Search by employee ID/name; Show more displays additional rows after the first 100. Close with X, Escape or backdrop click. Details use the shared snapshot without another server request; all employee fields are refreshed with the counts. After UI updates, restart the server and use Ctrl+F5.

## Review with sample data

Leave these settings in config.ini:

```ini
[application]
data_mode = demo
[database]
enabled = false
```

The dashboard labels sample data explicitly. Filter by employee unit/department; zero-punch groups remain visible. NULL assignments display as Not assigned, with blank strings labelled separately. Existing unit names remain unchanged. Global source coverage includes unmapped IDs outside the filtered totals.

## Enable SQL only after performance review

Review IO/TIME and actual plans from 002 first. The application's summary SELECT in sql/003_attendance_dashboard_summary.sql consolidates the counts using a full outer join; it has NOT been measured on SQL Server. For an SSMS measurement, copy its text into a query window for SPEL_ATTENDENCE and replace its two ODBC question-mark parameters with declared datetime variables @Start and @End. Use the same half-open calendar-day range and STATISTICS IO/TIME/actual-plan instructions as 002. Do not run the raw question-mark template in SSMS.

After reviewing query performance and confirming CHECKTIME is Pakistan local time, fill database credentials locally, then set:

```ini
[application]
data_mode = live
[database]
enabled = true
[cache]
enabled = true
ttl_seconds = 60
```

Restart python serve.py. Opening the dashboard in live mode initiates SQL SELECTs. Application startup alone does not connect. The 60-second TTL is an initial configurable value, not a measured production recommendation. No background polling or forced refresh: page loads/filter submissions reuse the shared snapshot until expiry. Cache is shared only inside one process; multiple workers or app instances require another caching design before deployment.

SQL uses fixed SELECT text and parameterized dates. Current application query: sql/dashboard/employee_snapshot.sql (003 is retained as a prior summary reference). The preflight checks target database and read-committed session isolation; the SELECT reads employee detail fields with deduplicated today's IDs and device unit-location mappings. The application deduplicates employees and derives all tiles from those rows. Connection and query timeouts apply; connections/cursors close after reading. No migrations, tables, views, indexes, database-setting changes, data modification or dirty-read hints are used. The source database is SPEL_ATTENDENCE.

Development sa is allowed as requested. Driver read-only mode and connection intent are advisory; use a SELECT-only account before deployment. Store passwords only locally or in the documented environment overrides. Do not include config.ini in ZIPs or share connection strings.

The page shows the last successful read time (not last machine sync). Failed refreshes show same-day cached data as stale; no successful snapshot produces HTTP 503 instead of sample/zero counts. Retries back off for the cache TTL. Yesterday's data is never substituted for today. Read committed can block writers/readers and does not guarantee a point-in-time snapshot; measure load before scheduling wider use.

If unavailable, check ODBC Driver 17, server access, credentials, certificate trust, database name and isolation. The page deliberately hides raw driver errors and credentials. Do not disable encryption or change database settings to bypass an error without diagnosing it.

Verify offline: python -m unittest discover -s tests -v. Tests use sample records and mocked SQL connections, not local credentials.
