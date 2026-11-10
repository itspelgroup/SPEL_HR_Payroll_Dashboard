# LAN deployment

The easiest Windows deployment is one central server running the dashboard in
a single Waitress process. All desktops visit that server; do not install a
separate running instance at each location.

## Quick start (sample data)

1. Copy the project folder to the Windows server. Do not copy a developer
   `.venv`; the launcher creates a local environment and installs requirements.
2. Install Python 3 and ensure the server has internet access for the first
   dependency install.
3. Double-click `start-lan.bat`. It binds Waitress to all network interfaces
   (`0.0.0.0`) while leaving `config.ini` and database settings untouched.
   Without a local `config.ini`, the dashboard uses the sample-data defaults.
4. Open an elevated PowerShell in the project folder and allow inbound access:

   ```powershell
   .\allow-lan-firewall.ps1
   ```

   This opens TCP 5000 only for the local subnet, and only on Domain/Private
   firewall profiles. For routed company/VPN networks, specify the trusted
   client ranges instead, for example:

   ```powershell
   .\allow-lan-firewall.ps1 -Port 5000 -RemoteAddress '192.168.11.0/24','192.168.20.0/24'
   ```

5. On the server, run `ipconfig` and find the IPv4 address of the active LAN
   adapter. Reserve that address in DHCP or assign a centrally managed static
   address. On each desktop, browse to `http://SERVER-IP:5000`, for example
   `http://192.168.11.25:5000`.

`192.168.11.1` is often the router/gateway address, not the Windows server.
Use the address shown on the server itself. Clients at other physical sites
need corporate routing/VPN and firewall authorization; do not expose this port
to the public internet or configure router port forwarding.

## Use real dashboard data

Sample mode is suitable only to test reachability and layout. Before using
employee or payroll data:

1. Copy `config.example.ini` to the private `config.ini` on the server. Keep
   `config.ini`, account files, and `instance/` out of shared ZIPs and source
   control.
2. Configure the `[database]` connection with a dedicated SQL **read-only**
   account, then set:

   ```ini
   [application]
   data_mode = live

   [database]
   enabled = true

   [cache]
   enabled = true
   ttl_seconds = 60

   [security]
   enabled = true
   password_storage = hash
   cookie_secure = false
   ```

   Keep the port at `5000` unless you also change the firewall rule and user
   URL. `start-lan.bat` supplies the network bind at launch and overrides only
   `application.host`; it does not rewrite `config.ini`. The application
   refuses to bind live data to a network interface unless authentication is
   enabled.
3. Restart `start-lan.bat`. On the server itself, open
   `http://127.0.0.1:5000/setup` to create the first administrator if no
   accounts exist. Setup is restricted to localhost. Sign in, then create
   individual accounts and grant only the needed tabs and locations in
   **Settings**.
4. Restrict filesystem access to the service/operator account and
   administrators. Install the SQL Server ODBC driver on this server and
   verify it can reach SQL Server.

HTTP on a trusted LAN is a convenience for initial testing, not encrypted
transport: passwords and session traffic are not protected from network
observers. For sensitive or routed multi-location use, put Waitress behind an
HTTPS reverse proxy, set `cookie_secure = true`, and distribute only the HTTPS
URL. Keep Waitress bound to `127.0.0.1` when the reverse proxy is on the same
machine rather than using the LAN launcher.

## Operations

- Keep one running server process so in-memory caches and login throttling are
  shared. Keep the server awake and connected to the LAN.
- `start-lan.bat` is an interactive launcher; its console must remain open.
  For automatic startup/recovery, install a Windows service using the
  organization's approved service manager and run it under a restricted
  service account.
- If changing requirements after the first launch, update the environment
  with `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- If clients cannot connect, check the server IP, that the server is running,
  the configured TCP port, Domain/Private firewall profile, client subnet
  range, and corporate routing/VPN. The firewall script requires elevation.
