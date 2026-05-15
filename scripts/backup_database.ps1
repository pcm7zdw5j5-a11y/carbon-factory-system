$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DatabasePath = Join-Path $ProjectRoot "carbon_factory.db"
$BackupDir = Join-Path $ProjectRoot "backups"

if (-not (Test-Path $DatabasePath)) {
    Write-Host "Database not found: $DatabasePath"
    Write-Host "Run the system once first, then try backup again."
    exit 1
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupPath = Join-Path $BackupDir "carbon_factory_$Timestamp.db"
Copy-Item -LiteralPath $DatabasePath -Destination $BackupPath

Write-Host "Database backup created:"
Write-Host $BackupPath
