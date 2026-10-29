# Dashboard query catalog

Runtime SQL lives in this folder. No SQL is embedded in the Python provider.
All files are read-only SELECTs; no migrations or automatic SQL-file execution.

| Query | Used by | Parameters |
| --- | --- | --- |
| connection_preflight.sql | Connection/database/isolation validation before loading a snapshot | None |
| employee_snapshot.sql | All attendance tiles, Location/Unit filters, unit tiles and employee popup rows | Inclusive day start, exclusive next-day start (ODBC `?` markers) |

## Tile and data-view definitions

These views deliberately reuse one shared employee snapshot. They do not each
send a separate SQL query, and opening/searching a popup does not contact SQL.
The provider deduplicates employees and unit-location rows before counting.

| Tile or view | Snapshot selection / calculation | Implementation |
| --- | --- | --- |
| Registered IDs | Matched zkk_Employees rows in selected Location/Unit | app.py attendance route |
| Punched today | Registered selection with a matching distinct today's USERID | app.py attendance route |
| No punch recorded | Registered minus punched in selected scope | app.py attendance route |
| Unmapped punched IDs | Today's distinct USERID without employee match; all locations | dashboard/attendance.py; app.py |
| Unit tile | Registered and punched selections grouped by employee Unit | app.py attendance route |
| Location filter | Employee Unit matched to zkk_Devices.Unit/Location; unique locations | employee_snapshot.sql; app.py |
| Unit filter | Units available within selected Location | app.py; static/dashboard.js |
| Registered popup | All selected mapped employees | static/dashboard.js |
| Punched popup | Selected mapped employees with today's punch | static/dashboard.js |
| No-punch popup | Selected mapped employees without today's punch | static/dashboard.js |
| Unmapped popup | All unmatched punched IDs, regardless of filters | static/dashboard.js |
| Unit popup | Selected mapped employees belonging to clicked Unit | static/dashboard.js |
| Popup ID/name search | Client-side search within the popup's selected records | static/dashboard.js |
| Global source coverage | Mapped punched + unmapped, all locations | app.py attendance route |

Name selection is in dashboard/attendance.py: use Name when usable, otherwise
PName, otherwise Name unavailable. Source values are never modified.

## Performance and maintenance

The date predicate leaves CHECKTIME unmodified so existing indexes remain
available to the optimizer. Multiple IN/OUT machines must not multiply employee
counts. The shared snapshot cache serves all users/threads in one process;
filters and popups do not bypass it. Do not add per-tile polling.

For SSMS testing, use sql/002_attendance_performance_test.sql as the collection
guide. Copy employee_snapshot.sql into an isolated query window, replace the two
`?` markers with declared datetime variables, and collect STATISTICS IO/TIME and
the actual execution plan. Do not execute this entire folder automatically.

sql/000, 002, 010 and 020 are manual diagnostic scripts; sql/003 is the prior
summary approach. sql/001_create_attendance_destination.sql is a paused historical
proposal and must not run. The former sql/004 query was moved here.
