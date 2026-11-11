# Changelog

## Attendance alert query and tiles - 2026-11-10
Expanded the inferred presence window to 96 hours and aligned Attendance Alerts with the user's base query: only employees whose latest unambiguous event is IN are in scope. Retained only In Premises, Over 12 Hours, From Other Location, and Guest tiles. Location options and counts use `InPremLocation`. Moved the separate Branch Name, Unit, and Department employee summary grids from the In Premises popup onto the main page under the tiles; all remain scoped by the selected location. Removed missing-punch/review tiles. Added payroll branch and last IN/OUT detail. No database changes.
Optimized the bounded punch query to classify once and use window aggregates instead of repeated latest-event and last-punch aggregation joins. Preserved latest-event timestamp ties and kept CHECKTIME filter sargable. Guest IDs are excluded from From Other Location; over-12-hours uses the base query's two-decimal comparison.
Added a live-only deployment payload with a locked live-mode config template, empty hashed-password account store, and launcher that validates live settings. Demo providers load lazily so the runtime ZIP can omit demo data, tests, and development references.

## Continuous monthly graph - 2026-11-07
Restored a shared-axis vertical monthly bar graph; removed individual month cards/header pills and automatic monthly horizontal orientation. Narrow displays scroll across the graph; bright current/muted prior bars, three values and drilldowns are retained. 19 targeted Python and 42 JS checks pass; visual review pending. No SQL/configuration changes.

## Multi-user Settings and INI accounts - 2026-11-07
Added admin Settings with account creation/edit/disable/password reset, multiple allowed tabs and locations, self-service password changes, localhost bootstrap and explicit HR-unit mappings. Activated local authentication and migrated the existing admin hash without SQL Server access; new/reset passwords use the requested plaintext INI storage with optional hashing. Enforced scopes before all dashboard response payloads; added CSRF, session revocation and account recovery. 102 offline tests pass; network deployment and visual QA pending. See docs/DASHBOARD_ACCOUNTS.md.

## HR page clipping and bright month panels - 2026-11-07
Scoped HR-only document scrolling overrides the inherited wall-page overflow lock. Moved compact YTD tiles before the graph and fit chart height to remaining viewport/dialog space, including filter changes. Brightened month cards with blue gradients, cyan borders and large uppercase header pills, with horizontal spacing adjusted. 19 targeted Python tests, 37 JS helper and 5 viewport checks pass; visual browser QA pending. No SQL/database/config changes.

## Clearer comparison bars and month groups - 2026-11-07
Brightened current-FY bars, made prior-FY bars muted but visible, increased bar width/thickness and made all three values bolder/larger. Added distinct shaded bordered partitions and month badges for monthly pairs, with spacing adjusted for both orientations. Updated asset versions. Sample routes and 37 V8 checks pass; no data/query changes.

## Simplified current/prior FY comparison - 2026-11-07
Replaced generic comparison controls with fixed Monthly current-vs-previous FY month pairs and Yearly all-history FY totals plus current YTD. Removed range/custom-date/orientation/manual-period menus, retained optional dimension filters. Bars show working, OT and total separately; total remains a label/cap, never a duplicated segment. Three YTD tiles and exact-value table replace diagnostics. All-history aggregate verified ~0.424s; 83 Python and 37 V8 checks pass. Screenshot unavailable; no database changes or commit/push.

## Fit HR graphs to the screen - 2026-11-07
Replaced fixed-width SVG sizing with measured responsive layout and resize handling. Added Auto/Vertical/Horizontal orientation and expanded graph dialog. Moved the graph above compact summary tiles, widened the page and preserved exact values in tooltips/table while compacting chart labels. 80 Python and 29 V8 checks pass, plus sample HTML/control checks. Visual browser QA remains pending; no SQL/database/config changes.

## Fiscal July–June graphs - 2026-11-07
Changed HR monthly/yearly comparisons to fiscal years with July–June ordering, first/last FY selectors and optional custom dates. One stacked net/OT bar carries a total marker/label; added legend, fiscal bands and explicit graph axis names. Current periods are partial and future months Upcoming; future dates are excluded from query bounds. Fixed fiscal-year detail drilldown across January. 80 Python and 21 V8 helper checks pass. No SQL execution/DB changes; visual QA pending.

## Monthly/yearly HR comparisons - 2026-11-07
Added SQL-aggregated monthly/yearly views with net/OT/total graphs, selectable series and two-period hour/percentage deltas. Applied confirmed Total = Net + Overtime in tiles, graphs and popups; changed OT share denominator to total. Removed Source filtering. Kept bounded daily employee details with monthly drill-through. Partial selections, record coverage and missing periods remain explicit. Four-year read ~0.376s for 6,930 grouped rows; 74 Python and 14 V8 helper checks pass. No database changes; browser QA pending.

## HR Hours / SBO_AI - 2026-11-07
Evaluated HR_MIS/HR_MIS_C schemas, history ranges and absent indexes. Added HR Hours tab with six insight tiles, date/unit/department/worker filters, daily chart and cached searchable employee/grouped detail popups. Signed adjustments and repeated rows remain included with review flags. Bounded SELECTs, schema inventory and manual performance script saved separately. Seven-day live check ~0.213s; 64 Python checks pass. Browser QA incomplete. No database changes; earlier uncommitted development preserved.

## HR/Payroll source decision - 2026-11-07
Recorded SBO_AI as the database for upcoming HR and Payroll dashboards, superseding the earlier SBO_PAYROLL source plan for new modules. Attendance remains on SPEL_ATTENDENCE. Next step is a read-only schema inventory and source/key validation before choosing tiles and measuring queries. No SQL executed or database/configuration changes made.

## Canonical employee name sources - 2026-11-03
Changed attendance snapshots, alert roster and active employee directory queries to select PName directly from zkk_Employees. Removed Name-first fallback and duplicate Name/PName popup columns. Machine punch names continue to come from PName and now use the same blank-name formatting. Recorded zkk_Employees_Payroll.Name as the canonical field for future payroll-table integration; no unsupported join was introduced. Added source-policy regression checks. No database values were modified.

## Waitress queue pressure - 2026-11-03
Moved worker count from hard-coded 4 to [server] threads (default/local 8). Warm-cache readers no longer wait behind an in-progress database refresh; one request refreshes while others reuse the last same-day snapshot. Cold start and rollover retain single-load protection. Automatic refresh now initiates only one reload rather than potentially repeating it each second while a navigation is pending. Added worker-setting and concurrent-refresh regression tests. No queue-warning suppression, live SQL or database changes were performed; production timing is still needed to confirm the observed cause.

## v0.3.0 development checkpoint - 2026-11-02
Saved machine monitoring, 72-hour attendance alerts and active biometric Employees tabs with location-based scopes and tile-only staff screens. Shared popups provide unit/department filters, location/review filters, search, sorting and grouped counts. Designation is deferred at the user's request; removed its placeholder, data fields and filter. Authentication remains deferred/off by default. Local config, account stores and credentials remain excluded. Validation: 49 Python tests and 8 JavaScript checks; no live-query, browser or deployment verification claimed.

## Tile-only staff dashboards and shared filtered popups - 2026-11-02
Removed unit/department detail blocks from Employees and Attendance Alerts main screens. Every tile now opens a shared employee popup with cascading Unit/Department/PhysicalLocation filters, search, sorting, reset and unit/department counts; alerts add IN machine location and review reason. Main totals remain location-scoped while popup filtering is local to the clicked tile. Added an optional designation field/control, unavailable until the source table/column is confirmed. No designation database column or payroll join was invented. Removed obsolete popup scripts/templates and detail-block CSS. All 49 Python tests and 8 JavaScript filtering/grouping checks pass; browser interaction and live-query verification were not performed.

## Active Employees tab - 2026-11-02
Added Employees as the third tab, with active biometric employee totals, unit/department grouping and searchable popup details from zkk_Employees.Active=1. Location uses employee PhysicalLocation; local Unit and Department filters scope counts and details together. Active status is explicitly distinguished from payroll employment. Read-only SQL remains in sql/dashboard/, and the new employee_directory INI section controls page/cache refresh. No punch queries or machine joins are used for this directory.

## On-demand department breakdown - 2026-11-02
Made Unit / Department Detail a native expandable section, collapsed on first visit. Its unit filter and compact cards are shown only when expanded. Open/closed preference is retained within the browser session across automatic refreshes. Main alert tiles remain visible. Verified the sample route renders successfully without a live database connection.

## Compact unit cards and primary alert emphasis - 2026-11-02
Enlarged the main attendance alert tiles and totals. Reworked secondary detail into side-by-side unit cards with blue unit headings, indented department rows, aligned coloured count headings and muted zero counts. Retained unit filtering and all scoped popup actions. Fixed deferred-account SQLite connection cleanup and updated outdated offline test setup/expectations exposed when terminal execution became available. All 42 offline tests pass; no live SQL was executed. Native browser screenshot capture did not produce an artifact, so visual verification remains limited to the supplied screenshot and rendered HTML.

## 72-hour alerts and directional machine layout - 2026-10-31
Extended the configured attendance window from 48 to 72 hours. Kept only Location in the shared banner; moved Unit filtering into the attendance detail panel. Replaced the wide unit/department grid with grouped, compact department rows and individually clickable count indicators. Machines now use separate IN/OUT blocks with configurable blue/violet direction accents and independent red/green activity indicators; unrecognized names remain separate. Extracted shared banner/card/popup templates and updated grid fitting for multiple sections. Added layout/filter/window regression coverage; automated tests, browser checks and SQL performance validation remain pending due to terminal startup failure.

## Compact alert grid and shared RGB theme - 2026-10-31
Renamed the location-difference tile to From Other Location. Replaced unit/department tiles with a compact detail grid and added a Unit dropdown that scopes counts, grid rows and popup data together. Invalid unit selections reset after location changes. Shared configurable RGB indicators apply to both tabs: green presence/recent activity, amber extended stay, blue location differences, red review/delayed machine activity. Added filter regression checks; execution and browser verification remain pending due to terminal startup failure.

## Direction from machine Name - 2026-10-31
User confirmed that zkk_Devices.Name contains the authoritative IN/OUT direction. Presence now derives direction from complete, case-insensitive name tokens and joins punches by SENSORID/DeviceCode. Names with neither or both directions remain unresolved. Removed the live CSV direction-map setting. Parser regression cases added; automated execution remains unavailable.

## Presence exceptions and assigned-location differences - 2026-10-31
Removed registered counts from Employees metrics and groups. Added different-assigned-location tile for inferred-inside employees whose nonblank PhysicalLocation differs from their last IN machine location. Comparison normalizes case/spacing with optional explicit INI aliases. Added needs-review details and reasons for unknown directions, conflicting timestamp ties, future events, ambiguous IN locations and missing employee location assignments. Unknown assignments are not mismatches. No-event records remain unclassified. Documented missed/delayed OUT, repeated IN and lookback limitations. Regression tests added; execution, browser checks and live data verification remain pending because the terminal cannot start.

## Employees tab - 2026-10-31
Added a second tab with retained location selection, biometric roster counts, inferred inside counts and employees over the user-confirmed 12-hour threshold. Presence location uses the last IN machine, as requested. Unit/department tiles open searchable cached employee details including IN time and elapsed duration. Direction comes from the confirmed device map, not CHECKTYPE. Later OUT, conflicting ties, unknown sensors and future timestamps are handled conservatively. Added separately configurable refresh, 48-hour inference window, threshold and location basis. All SQL is in sql/dashboard/. Tests added; execution, browser QA and production-query performance checks remain pending because the workspace terminal cannot start.

## Configuration organization and machine cleanup - 2026-10-31
Added dashboard, machine_activity, punch_history and wall_display settings to local/example INI. Machine cache and automatic page refresh use dashboard.auto_refresh_seconds; activity indicators and popup labels follow configured thresholds, and TOP (?) history count is parameterized. Removed unused summary/status-total calculations and redundant latest-user join/receipt lookup. SQL remains in sql/dashboard/. Configuration guide added; offline/browser verification is pending due to terminal startup failure.

## Single-screen machine wall - 2026-10-31
Replaced page headings and location sections with one banner containing the Machines tab, location filter and ticking Pakistan clock. Machine cards show only name, red/green activity indicator, latest punch datetime and latest punched employee ID/PName/unit. ResizeObserver calculates grid columns, rows and typography to fit the available viewport; page scrolling is disabled while punch history can scroll inside its dialog. Location selection and cache-based refresh remain. Added/updated rendering checks; execution and browser validation remain blocked by terminal startup failure.

## Authentication deferred - 2026-10-31
At the user's request, disabled authentication by default in both live and demo modes. Location remains the baseline scope for dashboard design and filters. Existing account code remains available for later explicit activation. Location selection currently filters data without restricting access.

## Large-screen machine activity and recent punches - 2026-10-31
Removed machine unit labels; devices display location only. Expanded popups to the latest 15 employee punches per device, ordered by CHECKTIME then ID, with USERID, PName, employee Unit, PhysicalLocation, punch time and receipt time. Machine activity now follows CHECKTIME; green indicates age strictly under 10 minutes and excludes future timestamps. Larger typography, cards and dialog history support distant viewing. History loads only at shared-cache refresh, never per click. Added SQL-provider, rendering and threshold regression tests; execution, browser verification and query performance review remain pending due to terminal failure.

## Location machine cards and dashboard accounts - 2026-10-31
Replaced summary/activity tiles with a black machine-only dashboard grouped by device location. Each machine opens its own last-received-punch popup with USERID, CHECKTIME, PName and PhysicalLocation; ties use attendance ID. Latest punch time remains distinct from database receipt time. Added local hashed-password accounts, administrator/all-location and assigned-location roles, server-enforced machine scope, sign-in/out, CSRF protection, cookie sessions, request throttling and no-store responses. Authentication defaults on for live mode. Account database/session key are excluded under instance/. Location accounts cannot access the unscoped legacy attendance route. Added authorization regression coverage; tests, browser QA and SQL performance checks remain unverified because the terminal cannot start.

## Machine tiles and automatic refresh - 2026-10-31
Removed visible machine tables; total machines, latest receipt, inactive devices, activity statuses and location tiles open scoped details in a native dialog. Inactive follows zkk_Devices.Active=false, separate from receipt age. Location changes apply automatically. Refresh uses the configured cache interval and retains the URL filter; it pauses while a dialog is open or the tab is hidden. Tile clicks reuse rendered snapshot details without SQL requests. Browser and automated verification remain pending due to unavailable terminal execution.

## Machine overview - 2026-10-31
Home now shows device inventory, location machine counts and per-device receipt activity. Attendance moved to /attendance. Status thresholds confirmed by user: Recent within 60 minutes, Delayed up to 1440 minutes, No recent punches thereafter; disabled and never-received devices remain visible. Receipt age uses MAX(InsertedAt), latest punch uses MAX(CHECKTIME), matched by SENSORID/DeviceCode. A separate shared machine snapshot avoids loading employee details on the home page. New read-only aggregate query has not been executed or performance-verified; offline tests added but cannot run because the workspace terminal fails to start.

## Device-based location catalog - 2026-10-31
Location options now come from distinct zkk_Devices Location/Unit pairs in a read-only query cached with the employee snapshot. Device locations and units remain selectable even without roster employees. Unit options follow the selected device location; incompatible unit selections reset. Case-only location variants remain unified. Added offline regression coverage; execution pending because the workspace terminal cannot start. No live SQL or database changes performed.

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
