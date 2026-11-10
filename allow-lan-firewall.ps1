#requires -RunAsAdministrator
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5000,
    [string[]]$RemoteAddress = @('LocalSubnet')
)

$ErrorActionPreference = 'Stop'
New-NetFirewallRule `
    -DisplayName 'SPEL HR Payroll Dashboard (LAN)' `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -Profile Domain,Private `
    -RemoteAddress $RemoteAddress `
    -Description 'Allow dashboard access only from approved private LAN/VPN address ranges.'
