# Dashboard settings
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
lookback_hours = 48
location_basis = last_in_machine
```

The Employees tab is /employees. Location is preserved when switching tabs. Registered counts refer to the biometric roster, mapped to device location through employee unit. Inside and long-stay counts use the last IN machine's location; they can differ from the roster assignment. Last known IN without a later OUT is an inference, not proof of physical presence. Only the configured lookback is examined. No event, older events, unknown directions and conflicting timestamp ties do not establish presence or absence. A missed OUT can overstate inside time. Over-threshold means strictly greater than long_stay_hours.

Direction follows the user-confirmed naming convention in zkk_Devices.Name: a complete IN token means entry; a complete OUT token means exit. Matching ignores case and accepts separators such as hyphens, spaces and underscores. Names containing both or neither are unresolved. MAIN and PRINT do not count as IN. Punch SENSORID joins to DeviceCode; DeviceCode text and CHECKTYPE do not determine direction. Names are refreshed with each employee snapshot. employee_roster.sql, employee_devices.sql and employee_latest_events.sql contain the read-only runtime queries. Timestamp ties remain available for ambiguity detection. Query performance remains unverified.

The registered count has been removed from the Employees tab. Its tiles now show inferred inside, over-threshold, different assigned location, and needs review. Different assigned location compares nonblank employee PhysicalLocation to last IN machine location, ignoring case and repeated/outer spaces. Missing assignments are reviewed, not counted as mismatches. Optional aliases can reconcile equivalent labels; both alternate and canonical labels should map to the same canonical spelling. Do not alias genuinely different sites. Location mismatches are assignment differences, not proof of unauthorized attendance.

Presence limitations: a missing or delayed OUT can overstate inside counts; repeated IN punches can understate elapsed time. Unrecognized directions, mixed IN/OUT ties and future timestamps are excluded and shown with review reasons. An IN tied across different locations is unresolved in each relevant location. Records with no event in the window are unclassified, not absent. Missing PhysicalLocation is a review item but does not itself invalidate the inferred IN. Long-stay, mismatch and review tiles can overlap; do not sum them to obtain a headcount. Device clocks, SQL timezone, direction mapping and actual query load still require live verification.

Attendance Alerts now uses a compact unit/department grid with a Unit dropdown beside Location. Both selections scope all alert metrics, grid rows and popup records; invalid units reset to All units after a location change. From Other Location is the display name for the assigned-location mismatch count. The shared ui_colors section uses RGB components (each 0–255): healthy=green, attention=amber, information=blue and critical=red. Both tabs use the same theme. Text labels accompany colour to avoid relying on colour alone.

Latest layout (2026-10-31): lookback_hours is now 72 in local and example settings. The banner contains only the Location filter. Unit is inside the Unit / Department Detail panel; it still scopes the alert metrics and popups. Compact department rows are grouped under unit headings with clickable inside/extended-stay/other-site/review counts. Machines are separated into IN, OUT and (when needed) unknown-direction sections based on device Name tokens. direction_in and direction_out in ui_colors control their independent RGB accents; red/green still indicate punch activity. Shared banner and popup partials avoid duplicated markup. Extending the window can recover older unmatched events but does not resolve missed OUT punches or prove presence; validate query cost before deployment.
