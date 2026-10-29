# Attendance test results - 2026-10-29

## Subsequent live application verification
User authorized actual data after viewing sample mode. Assistant verified the SELECT provider: 1003 registered, 872 mapped punched, 2 unmapped (874 overall), 13 groups. Connection/preflight/summary fetch completed in approximately 0.10 seconds. No DB objects, data or settings changed. Local development certificate trust resolved a validation failure; encryption remains enabled. Full IO/TIME/plan/load analysis is still pending. The screenshot below is an earlier observation.

Source: user-provided SSMS screenshot. Assistant did not connect or execute SQL.

- Server: SAPSERVERX; SQL Server 2017 RTM, 14.0.1000.169, Enterprise Edition (64-bit).
- Database: SPEL_ATTENDENCE; compatibility level 100.
- READ_COMMITTED_SNAPSHOT: off; snapshot isolation: OFF.
- Session: read committed; open transactions: 0.
- Server-local time: 2026-10-29 13:39:57.590; UTC: 08:39:57.590 (UTC+5).
- Test date range: 2026-10-29 00:00 inclusive to 2026-10-30 00:00 exclusive.
- Distinct punched IDs: 872; unmapped punched IDs: 2.

| Employee unit | Registered | Punched today |
| --- | ---: | ---: |
| NULL | 18 | 11 |
| OFFICE | 42 | 37 |
| OFFICE_P | 60 | 44 |
| OFFICE-P | 3 | 2 |
| UNIT1 | 11 | 9 |
| UNIT2 | 165 | 144 |
| UNIT3 | 129 | 120 |
| UNIT4 | 46 | 45 |
| UNIT5RYK | 166 | 150 |
| UNIT6 | 77 | 67 |
| UNIT7 | 67 | 61 |
| UNIT8 | 212 | 175 |
| UNIT9 | 7 | 5 |
| Total | 1003 | 870 |

All displayed departments are NULL. OFFICE_P and OFFICE-P are distinct source values; no normalization is agreed. Unit-less records must remain visible. Punched totals reconcile: 870 mapped + 2 unmapped = 872. These are biometric roster counts, not employment or confirmed-presence counts.

Performance remains unassessed: STATISTICS IO/TIME Messages and actual execution plans were not provided. Server clock offset alone does not confirm the CHECKTIME timezone convention. The screenshot shows an sa connection; dashboard credentials must instead use a dedicated SELECT-only identity. No account creation or permission changes performed.

Next: collect Messages and actual .sqlplan files from the completed test; inspect logical reads, CPU/elapsed time, access paths, conversions and spills before selecting live queries and shared-cache refresh behavior. Do not change isolation or database objects. Then configure the local application connection without using sa or recording passwords in project records.
