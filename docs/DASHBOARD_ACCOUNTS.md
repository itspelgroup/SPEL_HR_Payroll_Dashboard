# Dashboard accounts and machine layout
CURRENT DECISION (2026-10-31): defer authentication. Default access requires no username/password in either demo or live mode. Location remains the baseline for dashboard data and filtering; access enforcement will be activated later. Account setup instructions below are retained for that future stage and are not required now.

Latest update: machine tiles show location, with no machine unit label. Popups contain the last 15 punch events (not distinct employees), newest CHECKTIME first with ID as tie-breaker. Employee Unit, PName and PhysicalLocation are resolved from the current employee record. Green activity is based on CHECKTIME strictly under 10 minutes old; future timestamps do not qualify. The black layout uses larger typography and three columns on typical wide screens, four at 1800px and above. Receipt timestamps remain separate from punch timestamps. The history SELECT is cached and has not been performance-verified.


The first screen groups machines under location headings. Desktop uses four cards per row; smaller screens reduce columns. Each machine card shows receipt activity and opens its last-received record details. PName and PhysicalLocation come from zkk_Employees joined to that record's USERID. No summary tiles or on-page tables remain.

## Account setup

Live mode requires sign-in by default. Stop the server, then create accounts from the project directory:

```powershell
python -m dashboard.users --username admin --admin
python -m dashboard.users --username pandoki --location "Pandoki"
python serve.py
```

Passwords are entered privately and must contain at least 12 characters. Repeat the command to change a password or assignment. Use exact device location names; comparisons ignore case and surrounding spaces. Administrators can select all locations. Location users receive only their assigned location's machine and employee-punch details in the HTML, even if they edit URL filters. The legacy attendance page is administrator-only until its separate location-scoping work is completed.

Accounts are stored as password hashes in instance/users.sqlite3; session signing key is instance/session.key. Both are ignored by Git. Protect and back up this folder locally. To use another folder, configure security.account_directory and pass the same path to the account command using --directory.

Optional local config.ini settings:

```ini
[security]
enabled = true
cookie_secure = false
```

Use cookie_secure=true behind HTTPS for network deployment. Demo mode remains unauthenticated unless enabled=true is set. No default account or password exists. Do not disable authentication for network deployment. Sessions expire after eight hours of inactivity. Login throttling is in-memory for the single Waitress process.

Auto refresh uses the existing cache interval, retains filters and pauses while a popup is open or the tab is hidden. Changing location applies immediately. Machine details require no additional query on click.

The new latest-receipt query has not been performance-tested. Validate its SQL plan and load before deployment. No production deployment or live query execution was performed for this change. SQL timestamps are displayed as Pakistan local time; confirm the server's timestamp convention.

Verify locally: python -m unittest discover -s tests -v. Test execution and browser verification remain pending in the assistant environment.
