# Multi-user dashboard access

Current decision, 2026-11-07: authentication is activated in local config.ini. This supersedes the older decision to defer accounts. Accounts are managed in Settings and stored in a private users.ini, independently of the SQL Server login. No SQL Server objects, data or settings are changed by account management.

## Recommended deployment

Run one central Windows server with one Waitress process (`python serve.py`). Give each person their own account; users at every location open the same server URL. This shares the existing application caches across users and keeps configuration, credentials and permissions in one place. Do not copy a separate running app to each location: that creates independent accounts and duplicate database load.

Place the server behind an HTTPS reverse proxy, and give remote locations access through the company network or VPN. Restrict inbound access to that network. Run Waitress as a Windows service for automatic startup/recovery when deploying; a service/firewall/proxy has not been installed by this change. Measure concurrent load before increasing threads or adding instances. INI storage supports a small internal installation in ONE process; it is not a distributed account service. For a larger deployment, migrate accounts to a dedicated identity provider or transactional account store.

## Open Settings

1. Restart `python serve.py` from the project directory.
2. Open http://127.0.0.1:5000 and sign in with the existing administrator account. Its former password hash is retained; migration does not recover plaintext passwords.
3. Choose **Settings**, create individual users, and select any combination of allowed tabs and locations. Administrators always have all tabs and locations. **All locations** also includes future locations.
4. Add exact location names if missing. For HR Hours, expand each location and enter its exact HR unit names, one per line. A unit may belong to only one location. No HR mapping is guessed from employee/device names; restricted users without a mapping get Access denied.
5. Users change their own passwords under their account name. Administrators can reset a password or uncheck Enabled. The last enabled administrator cannot be removed or demoted.

If there are no accounts, `/setup` creates the first administrator, accessible only from localhost on the server. There is no default username/password. If an existing administrator password is unknown, reset it locally (substitute the actual username):

```powershell
Set-Location C:\Projects\SPEL_HR_Payroll_Dashboard
python -m dashboard.users --username YOUR_ADMIN_USERNAME --admin
```

The command prompts privately for the new password. It uses the same local config.ini/user_file as the app; `--config` can choose another config. `--location` can be repeated for a regular account; Settings is the preferred way to manage permissions.

## Configuration

The local config.ini now includes:

```ini
[security]
enabled = true
user_file = users.ini
password_storage = plain
minimum_password_length = 8
cookie_secure = false
```

Paths are resolved from the project folder. `account_directory` (default `instance`) holds the persistent session signing key, not the new user records. The shareable config.example.ini keeps authentication disabled for sample tests; enable it before sharing real data. Restart the server after changing security settings.

Passwords are stored as readable text for new/reset passwords, as requested. They never appear in the Settings user list or browser session. Anyone with filesystem access to users.ini can read plaintext credentials: restrict Windows file permissions to the server service account and responsible administrators. Protect backups the same way. users.ini, config.ini, temporary user files and instance/ are ignored by Git and must stay out of release archives. Never serve the project directory as static files.

For deployment, `password_storage = hash` is recommended. It applies to future creates/resets; existing accounts keep their previous format until reset. Existing legacy SQLite accounts migrate once, read-only, only when the INI file does not exist, and their hashes remain hashes. Do not delete users.ini to reset access; doing so could reimport old legacy accounts. Use Settings or the recovery command.

The requested plaintext file format is illustrated in users.example.ini. Lists use JSON arrays, e.g. `tabs = ["machines", "hr_hours"]` and `locations = ["Pandoki", "Karachi"]`. Tab IDs are machines, alerts, directory and hr_hours. Settings uses atomic file replacement; prefer it over editing the file while the server is running. Passwords must be 8-512 characters by default, without surrounding spaces or control characters; percent signs and Unicode are supported. No passwords are supplied in the template.

## Sharing the server

After configuring accounts and HTTPS/VPN, expose the server through the reverse proxy. Keep `application.host = 127.0.0.1` when the proxy runs on the same server. Set `security.cookie_secure = true` for HTTPS. Users receive the proxy's HTTPS URL, not localhost.

For a controlled LAN connectivity check, run `start-lan.bat` on Windows. It binds Waitress on network interfaces without editing the private config. The optional `allow-lan-firewall.ps1` helper opens the configured port only to LocalSubnet; use `-RemoteAddress` to restrict access to corporate/VPN CIDR ranges. Users then browse `http://SERVER_IP:5000`. This is plain HTTP and sends login credentials without transport encryption, so use HTTPS for real multi-user access. See [LAN deployment](DEPLOY_LAN.md) for first-time setup. Live data cannot be network-bound unless authentication is enabled.

## Access enforcement and limits

Tab URLs are checked before loading data; hiding links alone is not authorization. Machines are scoped by device location; Attendance Alerts by the configured IN-location/unit basis, with unknown event locations denied for restricted users; Employees by PhysicalLocation and configured aliases. HR daily/monthly/yearly totals, filter options and popup payloads are limited to explicitly mapped units. The legacy `/attendance` page remains administrator-only. Source queries/caches are shared in server memory; each response is filtered independently before serialization.

Accounts are reloaded per request. Disable, reset and permission changes invalidate that account's existing sessions on the next request, including edits directly to its INI section. Location mappings apply on the next request. A page already open may retain data previously delivered until refreshed; access controls cannot retract a response already sent.

CSRF checks protect login/setup/account/settings/logout forms. Sessions use HttpOnly, SameSite=Lax cookies, a persistent signing key and an eight-hour idle lifetime; enable Secure with HTTPS. Login throttling is in memory (five failed attempts per username/client IP per 15 minutes), appropriate to the single-process deployment. Browser responses use Cache-Control: no-store. There is no account audit-history or enterprise identity integration in this increment.

Validation: 102 offline Python tests pass, including legacy-account migration, bootstrap, Settings create/edit/reset, CSRF, lockout, session revocation, multiple tab/location restrictions and HR scope across shared caches. Browser visual testing and network/load testing remain pending. No production SQL was executed for this increment.

References: [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) recommends password hashing; [Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/) covers session cookie and CSRF protections.
