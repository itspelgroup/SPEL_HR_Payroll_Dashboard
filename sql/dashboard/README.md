# Dashboard query catalog

## HR Hours (SBO_AI)

CURRENT fixed scopes: Monthly loads prior FY July through today and pairs
matching current/prior FY months. Yearly loads all SQL datetime history
(1753-01-01 through today), derives the earliest available FY and includes every
FY through current YTD. No arbitrary year cutoff or Source filter. The same
hr_hours_periods.sql aggregate and max-group guard serve both scopes, with
separate shared window caches. All three working/OT/total values are displayed;
only working and OT are stacked. See docs/HR_HOURS.md; older catalog notes below
describe earlier UI versions.

Current graph grouping is fiscal July–June. Existing monthly SQL groups roll up
to FY totals in dashboard/hr_comparison.py; no additional runtime query is needed.
One bar stacks net and OT with total separately labelled (not added a second
time). Future query dates are clipped to today; selected fiscal ranges still show
all July–June categories. Source/month/group caps and shared caching are retained.

Current monthly/yearly query: **hr_hours_periods.sql**, parameters max_groups+1,
start/end-exclusive repeated for both UNION ALL branches. Aggregates by calendar
month/unit/department/worker/direct in SQL; yearly totals roll up these groups.
Supplies net, OT, total working hours graphs, period comparisons and aggregate
popups. Total = NetWorkingHours_D + OvertimeAdjustment_D as confirmed by user.
No Source filter; all source rows stay combined. Long-range views share one
bounded aggregate cache per date window. hr_hours_records.sql remains the
31-day employee-detail provider, reached from monthly detail links. No new
database objects or per-tile polling. See docs/HR_HOURS.md.

| Query | Used by | Parameters |
| --- | --- | --- |
| hr_hours_preflight.sql | HR access/isolation validation | None |
| hr_hours_records.sql | All HR Hours tiles, filters, daily chart, employee and grouped popups | max_rows+1; start/end-exclusive repeated for both UNION ALL branches |

One bounded date-window cache supplies all HR views. Signed adjustments and
repeated source rows remain included. Tiles show net hours, OT adjustment,
distinct employees, employees with positive OT, OT per 100 net hours and review
records. Unit/department/worker/date groupings reuse those rows. See
docs/HR_HOURS.md for definitions and query evaluation. HR names use EmpName;
existing biometric displays use PName.

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

Attendance Alerts uses **employee_latest_events.sql** for the latest punch
event(s) per employee and last IN/OUT timestamps over the configured 96-hour
window. It classifies the bounded rows once and uses window aggregates to avoid
the former repeated aggregation/join of the punch CTE. The CHECKTIME range stays
sargable, and ties at the latest timestamp are preserved. **employee_roster.sql** also reads `BranchName` from
`zkk_Employees_Payroll`. Python resolves tied latest events, applies the
employee-unit location mapping, and creates the four tile counts: resolved
In Premises, over-12-hour, other-location, and guest. The latter three are
subsets of resolved In Premises employees. The In Premises popup groups the
same selected-location employees independently by branch, unit, and department.
Counts are inferred presence, not an authoritative physical headcount.

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
