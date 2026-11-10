# HR Hours - current simplified view

Latest monthly graph correction (2026-11-07): user reported the comparison no longer looked like a graph. Restored one continuous vertical monthly chart with a common hours axis and July-June paired Last/This bars. Removed per-month card backgrounds, gradient panels and header pills. Thin month separators and bottom labels retain grouping; current bright/prior muted colours, working/OT/total labels, popups and exact-value table remain. Monthly no longer auto-switches to a tall horizontal list: narrow displays scroll horizontally across a minimum 1100px plot, with normal page scrolling retained. Minimum monthly chart height is 480px for a useful plotting area. Yearly keeps its responsive orientation. CSS/JS asset versions updated.

19 HR comparison Python tests, 42 JS calculation/layout checks and offline monthly/yearly sample rendering checks pass. Browser visual QA remains pending. No SQL or configuration/auth changes in this increment. Next: restart the server, hard-refresh /hr-hours?analysis=monthly and review the common-axis graph at the user's normal screen size.

Visibility fix: HR pages override the machine wall's root overflow lock, so
page bottoms and long charts scroll normally. Totals are now above the graph;
chart height responds to remaining viewport/dialog space and filter expansion.
Month panels use bright blue gradients, strong cyan borders and large uppercase
month headers. 19 targeted comparison tests, 37 JS helper and five viewport
checks pass; actual browser visual verification remains pending. No SQL changed.

Visual refinement: current FY bars are bright and solid; previous FY bars are
muted but clearly visible with dashed edges. Bars are wider, values are larger
and bold, and each month pair has its own bordered/shaded panel and month-name
badge. This applies to responsive horizontal layouts too. Theme colours remain
derived from existing UI variables. No changes to scopes, totals or SQL.

## What the user sees

Two fixed views: **Monthly** and **Yearly**. Optional Unit, Department,
WorkerType and DirectWorker filters sit in one collapsed Filters section. View
switches retain applied filters. There are no fiscal-range selectors, custom
comparison dates, orientation controls or arbitrary two-period selectors.
Employee/daily details remain available through a small link and bar popups.

Monthly: twelve July-June groups, with Last year and This year bars side by side
for each matching fiscal month. January in the previous FY is compared with
January in the current FY, even though calendar years differ. The current FY
ends at today's data; unreached months say Not yet. The previous FY shows its
full recorded months. The current incomplete month is explicitly to date; it is
not automatically normalized to the previous year's elapsed days.

Yearly: every fiscal year from the earliest source record through the current
FY. The current FY is year to date, and older bars use their full recorded FY
windows. There is no arbitrary last-four/last-ten-year cutoff. Gaps show No data;
filters do not erase the historical FY axis. Earliest coverage is based on the
combined source, not just the selected unit/department.

Each bar has one green Working-hours part and one amber Overtime part. The blue
cap marks Total. Three values are always shown for each known bar: Working,
Overtime and Total. Total is not stacked again, which would double-count hours.
Working hours exclude overtime; **Total = Working + Overtime**. Chart labels may
be compact at narrow widths; exact values are available in the table and popup.
Previous-year bars are muted/dashed, current-year bars solid, and both are named
in the legend. Missing/future values are never invented as zero hours.

Only three summary tiles remain: current-FY YTD Working, Overtime and Total.
Each opens its current-year detail rows. Clicking graph bars opens grouped
monthly Unit/Department/WorkerType records, with links to bounded employee-day
records. Popups, search, expansion and resizing do not run SQL.

## Layout

The three current-YTD tiles appear above the graph, which fits the available width. Wide screens use paired
columns, narrow/dense screens use horizontal paired bars automatically. No
orientation choice is required. Expand graph opens a large native dialog;
Escape/close returns it to the page. Refresh pauses while dialogs are open.
Axes are explicitly Fiscal month/year and Hours; the legend names all measures.

## SQL evaluation and source definition

SBO_AI.dbo.HR_MIS and HR_MIS_C are matching 13-column user tables. Their UNION ALL
is structurally valid and intentionally retains all source rows. Runtime SQL
uses explicit fields and labels source provenance only in employee-day records;
there is no Source filter. Metadata: reference/hr_mis_schema.json.

Observed 2026-11-07: HR_MIS has 1,090,287 rows spanning 2023-07-01..2026-08-31;
HR_MIS_C has 63,457 rows spanning 2026-09-01..2026-11-07. Both were heaps without
indexes. These dates are observations, not permanent partitions. No objects or
indexes are created and no data/settings are modified. Read-only intent with sa
is advisory; production still needs a SELECT-only identity.

NetWorkingHours_D and OvertimeAdjustment_D are float(53). The period query sums
decimal(28,8) conversions, then displays two decimals. Signed adjustments and
repeated rows remain included. EmpName/SPELID identify this HR dataset; no
biometric or payroll-master join is invented. ProductionTime is not interpreted.

## Queries and cache

- sql/dashboard/hr_hours_preflight.sql: access and read-committed validation.
- sql/dashboard/hr_hours_periods.sql: same SQL monthly dimension aggregation for
  both views. Monthly loads previous FY July through today. Yearly reads the
  source's full valid SQL datetime history, starting 1753-01-01, through today,
  then derives the earliest available FY. It transfers monthly groups, not
  employee-day rows, and clips all future dates.
- sql/dashboard/hr_hours_records.sql: employee/daily view, maximum 31 days and
  50,000 raw records. Popup drill-through preserves a bounded month and scope.

Each date window has a shared five-minute process cache (max three windows).
Dimension changes reuse that view's snapshot. Monthly and all-history Yearly
use separate windows/caches. max_period_groups=50000 prevents unbounded transfer;
overflow fails without partial totals. The old max_comparison_years setting is
obsolete/ignored. Query timeouts and explicit connection cleanup remain active.
Heap scans still need production IO/CPU/blocking monitoring. Manual SSMS scripts
031 and 032 contain STATISTICS IO/TIME and actual-plan instructions. No script
folder runs automatically. Location-scoped accounts cannot access unscoped HR
hours if authentication is enabled; authentication remains deferred/off per
existing settings.

## Live fiscal-year check - 2026-11-07

The all-history grouped read took ~0.424 seconds and found four fiscal years:

| Fiscal year | Working hours | Overtime hours | Total hours |
| --- | ---: | ---: | ---: |
| FY 2023/24 | 1,619,653.16 | 191,577.10 | 1,811,230.26 |
| FY 2024/25 | 2,115,416.21 | 283,058.82 | 2,398,475.03 |
| FY 2025/26 | 2,144,223.56 | 237,488.97 | 2,381,712.53 |
| FY 2026/27 through 7 Nov | 735,837.83 | 185,646.21 | 921,484.04 |

Current YTD and prior full years are not equivalent durations. No extrapolation
is performed. This read timing is not full performance/load validation. Only
aggregate totals were printed, with no employee names/IDs.

Validation: 83 Python checks and 37 V8 helper checks pass. Browser visual QA is
unavailable: isolated headless Edge did not return a screenshot/DOM result.
Monthly/yearly sample pages render successfully. Local config/credentials were
preserved. Restart python serve.py and Ctrl+F5 to load the updated assets.
