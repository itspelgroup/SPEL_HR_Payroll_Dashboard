# Dashboard settings
Employee-name source policy (2026-11-03): always use SPEL_ATTENDENCE.dbo.zkk_Employees.PName for employee names. Never fall back to its Name field. When zkk_Employees_Payroll is used, its Name is the canonical employee name. No payroll-table integration currently exists, so no speculative join was added. Device names continue to use zkk_Devices.Name. Missing or blank canonical names show Name unavailable. Restart the app to discard older cached names.

Waitress worker settings: [server] threads=8. The server remains a single process so caches are shared. Values 1–64 are accepted. On cache expiry one request refreshes the database while concurrent requests reuse the existing same-day snapshot; cold loads and date rollover still wait for a valid new snapshot. Page reload scheduling allows only one navigation at a time. Queue-depth warnings mean workers were occupied, not necessarily that a request failed; persistent warnings or slow pages still require actual request/SQL timing review. Restart python serve.py after changing worker settings.

Latest interaction (2026-11-02): Employees and Attendance Alerts main screens now contain only summary tiles. Unit/department breakdowns, search, sorting and employee filters are inside each tile's popup. The banner Location remains the main server-side scope; legacy Unit/Department URL arguments no longer reduce main tile totals. Popup filters cascade within the clicked tile's records and run entirely on the cached, location-scoped data. Unit and Department count tiles open grouped employee counts and details. Alert popups additionally filter IN machine location and review reason; both support PhysicalLocation. Designation is deferred at the user?s request and is omitted from current popup filters and columns. Removed obsolete page-detail templates/scripts and consolidated popup rendering/filter logic.

The new Employees tab is /employee-directory; Attendance Alerts remains /employees. Employees reads only zkk_Employees with Active=1. Location uses employee PhysicalLocation (with configured location aliases), not machine unit or last punch. Unit and Department filters are in the data block; counts and popup details share those filters. Active is the biometric-system flag, not confirmed payroll employment status. Its shared snapshot/page-refresh interval is [employee_directory] refresh_seconds (10–3600 seconds). SQL is sql/dashboard/active_employee_directory.sql. Popups reuse cached rows and make no additional SQL queries.


Edit local config.ini. config.example.ini contains shareable defaults; local values override them. Restart python serve.py after changes. Never commit config.ini or share database credentials.

| Section | Purpose |
| --- | --- |
| application | Host, port, live/demo mode, Pakistan timezone |
| database | SQL connection, encryption and query timeouts |
| dashboard | Automatic page and shared machine-data refresh interval |
| employee_overview | Employee-tab refresh, long-stay threshold, event window, location basis and confirmed machine direction map |
| employee_location_aliases | Explicit equivalences for PhysicalLocation and machine-location comparisons |
| ui_colors | Shared healthy, attention, critical and information colours as three RGB components |
| machine_activity | Recent/green and delayed punch-age thresholds |
| punch_history | Number of recent punch events in a machine popup |
| wall_display | Reference card dimensions, gaps, compact breakpoint, font scaling |
| cache | Employee attendance cache interval; separate from machine refresh |

```ini
[dashboard]
auto_refresh_seconds = 60

[machine_activity]
recent_minutes = 10
delayed_minutes = 1440

[punch_history]
limit = 15
```

auto_refresh_seconds accepts 10–3600 seconds. It controls both automatic page reload and machine-cache expiry. Requests share the cached snapshot; filter changes and popup clicks do not bypass the cache. Refresh pauses while a popup is open or the tab is hidden. A refresh occurs on the next timer tick after returning. History limit accepts 1–100. Activity requires 0 < recent_minutes < delayed_minutes; future punches are not green.

All attendance-database queries live under sql/dashboard/. machine_snapshot.sql supplies device inventory and latest punch timestamps. machine_recent_punches.sql returns a parameterized number of recent punches per device with employee metadata. device_locations.sql supplies attendance filter options. SQL files are loaded by the providers, not executed automatically as a directory. No schema or data writes are performed.

Authentication is deferred and off by default. Retained account support is not part of the current machine screen.

Employee overview settings:

```ini
[employee_overview]
refresh_seconds = 60
long_stay_hours = 12
lookback_hours = 96
```

The Attendance Alerts tab is /employees. Its location filter and tile counts use the `InPremLocation` of rostered employees whose latest unambiguous event in the lookback is IN. The In Premises popup can break down those employees by Branch, Unit and Department; selecting a location scopes all three breakdowns. Over 12 Hours, From Other Location and Guest are subsets of the same selected-location employees and can overlap. Presence is inferred, not proof of physical presence. No event, older events, unknown directions and conflicting timestamp ties do not establish presence or absence. Over-threshold means strictly greater than long_stay_hours.

Direction follows the user-confirmed naming convention in zkk_Devices.Name: a complete IN token means entry; a complete OUT token means exit. Matching ignores case and accepts separators such as hyphens, spaces and underscores. Names containing both or neither are unresolved. MAIN and PRINT do not count as IN. Punch SENSORID joins to DeviceCode; DeviceCode text and CHECKTYPE do not determine direction. Names are refreshed with each employee snapshot. employee_roster.sql, employee_devices.sql and employee_latest_events.sql contain the read-only runtime queries. Timestamp ties remain available for ambiguity detection. Query performance remains unverified.

The registered count has been removed from the Employees tab. Its tiles now show inferred inside, over-threshold, different assigned location, and needs review. Different assigned location compares nonblank employee PhysicalLocation to last IN machine location, ignoring case and repeated/outer spaces. Missing assignments are reviewed, not counted as mismatches. Optional aliases can reconcile equivalent labels; both alternate and canonical labels should map to the same canonical spelling. Do not alias genuinely different sites. Location mismatches are assignment differences, not proof of unauthorized attendance.

Presence limitations: a missing or delayed OUT can overstate inside counts; repeated IN punches can understate elapsed time. Unrecognized directions, mixed IN/OUT ties and future timestamps are excluded and shown with review reasons. An IN tied across different locations is unresolved in each relevant location. Records with no event in the window are unclassified, not absent. Missing PhysicalLocation is a review item but does not itself invalidate the inferred IN. Long-stay, mismatch and review tiles can overlap; do not sum them to obtain a headcount. Device clocks, SQL timezone, direction mapping and actual query load still require live verification.

Attendance Alerts now uses a compact unit/department grid with a Unit dropdown beside Location. Both selections scope all alert metrics, grid rows and popup records; invalid units reset to All units after a location change. From Other Location is the display name for the assigned-location mismatch count. The shared ui_colors section uses RGB components (each 0–255): healthy=green, attention=amber, information=blue and critical=red. Both tabs use the same theme. Text labels accompany colour to avoid relying on colour alone.

Latest layout (2026-10-31): lookback_hours is now 72 in local and example settings. The banner contains only the Location filter. Unit is inside the Unit / Department Detail panel; it still scopes the alert metrics and popups. Compact department rows are grouped under unit headings with clickable inside/extended-stay/other-site/review counts. Machines are separated into IN, OUT and (when needed) unknown-direction sections based on device Name tokens. direction_in and direction_out in ui_colors control their independent RGB accents; red/green still indicate punch activity. Shared banner and popup partials avoid duplicated markup. Extending the window can recover older unmatched events but does not resolve missed OUT punches or prove presence; validate query cost before deployment.


## HR Hours - SBO_AI

```ini
[hr_hours]
refresh_seconds = 300
default_days = 7
max_range_days = 31
max_rows = 50000
cached_ranges = 3
```

The HR Hours tab reuses the existing server/credentials and reads fully qualified
SBO_AI tables without changing the attendance connection's default database.
Every date window shares one snapshot across unit/department/worker/source/direct
filters and popups. At most cached_ranges windows are retained. Row-limit overflow
fails without displaying partial totals. Empty dimensions can be selected apart
from All. No location mapping is invented; scoped non-admin accounts cannot access
this unscoped tab when authentication is enabled. See docs/HR_HOURS.md.


### Monthly and yearly HR hours

```ini
[hr_hours]
max_comparison_years = 10
max_period_groups = 50000
```

The Monthly (default) and Yearly views use a separately cached SQL monthly
aggregate. Daily max_range_days/max_rows still restrict employee-day details;
they do not restrict yearly charts. Existing refresh_seconds/cached_ranges
also apply to the separate period cache. No Source filter is used in any view.
Total working hours = net working hours + overtime; OT share uses total hours.
Manual long-range measurement: sql/032_hr_hours_monthly_yearly_performance.sql.


### Fiscal graph behavior

HR Hours uses the confirmed July?June fiscal calendar. First/last FY selectors
set full fiscal windows; custom dates can override them and are cleared when FY
selectors change. Monthly shows July?June, yearly groups months into FY totals.
Default current-FY months after today are Upcoming, and SQL bounds stop at today.
One stacked net/OT bar represents each period; total is a marker/label, with an
explicit legend and hours/fiscal-period axis labels. Runtime SQL/cache limits
are unchanged. No local credentials or config values were modified for this UI.


### Simplified HR comparison scope (current)

Monthly now always pairs the current and previous fiscal years by July-June
month. Yearly includes all available fiscal years plus current YTD. The old
max_comparison_years option is ignored; the max_period_groups guard remains.
Fiscal/date/orientation/manual comparison controls have been removed from this
screen. Optional dimensions live under Filters; daily employee dates remain
bounded by their existing limits. No local credentials or configuration changed.


### Multi-user security (current, 2026-11-07)

Local config.ini now enables `[security] enabled=true`, `user_file=users.ini`,
`password_storage=plain`. See [accounts configuration](DASHBOARD_ACCOUNTS.md).
Settings is administrator-only and controls allowed tabs and multiple locations.
HR restricted access now requires explicit HR-unit mappings in the same user file;
this supersedes the earlier blanket denial for all scoped users. No mappings are
inferred. The SQL server/user/credentials are separate and unchanged.
The example config remains public sample mode; explicitly enable security before
sharing real data. One Waitress process shares caches across all sessions.
