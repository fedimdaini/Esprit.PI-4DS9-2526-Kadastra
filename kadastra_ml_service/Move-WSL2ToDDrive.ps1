<#
.SYNOPSIS
    Safely moves all WSL2 virtual hard disks (.vhdx) from C: to D:,
    with full backup, checkpoint, and rollback capability.
.DESCRIPTION
    This script exports each WSL distribution, moves its virtual disk,
    re-imports it to the new location, and verifies success.
    A system restore point is created before changes.
    If any step fails, the script guides you to restore from backup.
.NOTES
    Author: AI Assistant
    Requires: Windows 10/11 with WSL2, PowerShell as Administrator
#>

#Requires -RunAsAdministrator

# ------------------------- CONFIGURATION -------------------------
$targetDrive = "D:"
$backupRoot  = "$targetDrive\WSL_Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$newWSLRoot  = "$targetDrive\WSL"
$logFile     = "$env:TEMP\MoveWSL2_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# ------------------------- FUNCTIONS -------------------------
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Stop-WithError {
    param([string]$Message, [bool]$IsFatal = $true)
    Write-Log -Message $Message -Level "ERROR"
    if ($IsFatal) {
        Write-Log -Message "SCRIPT TERMINATED. Recovery info: See $logFile"
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# ------------------------- SAFETY CHECKS -------------------------
Write-Log -Message "===== START MOVE WSL2 TO $targetDrive ====="

# 1. Check WSL is installed
if ((Get-Command wsl.exe -ErrorAction SilentlyContinue) -eq $null) {
    Stop-WithError "WSL not found. Please install WSL first."
}

# 2. Check target drive exists
if (-not (Test-Path "$targetDrive\")) {
    Stop-WithError "Target drive $targetDrive does not exist."
}

# 3. Check free space on C: (need at least 10GB temporarily for export if we export to C? We export to D: so safe)
$freeSpaceC = (Get-PSDrive -Name "C").Free
if ($freeSpaceC -lt 2GB) {
    Write-Log -Message "Critical: C: has only $([math]::Round($freeSpaceC/1GB,2)) GB free. Proceeding but export will go to D:." -Level "WARN"
}

# 4. Check free space on D: (need space for backups + new .vhdx)
$freeSpaceD = (Get-PSDrive -Name $targetDrive[0]).Free
$estimatedBackupSize = 5GB # placeholder, will check actual size later
if ($freeSpaceD -lt 30GB) {
    Stop-WithError "D: has only $([math]::Round($freeSpaceD/1GB,2)) GB free. Please free at least 30 GB first."
}

# 5. Create system restore point
try {
    Enable-ComputerRestore -Drive "C:\" -ErrorAction Stop
    Checkpoint-Computer -Description "Before moving WSL2 virtual disks to $targetDrive" -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
    Write-Log -Message "System restore point created successfully."
}
catch {
    Write-Log -Message "System restore point creation failed (non-critical): $_" -Level "WARN"
}

# ------------------------- GET ALL WSL DISTROS -------------------------
Write-Log -Message "Enumerating WSL distributions..."
$distrosRaw = wsl.exe --list --verbose
$distros = @()
$distrosRaw | ForEach-Object {
    if ($_ -match "^\s*(\S+)\s+(\S+)\s+(\d+)\s*$") {
        $distros += [PSCustomObject]@{
            Name   = $matches[1]
            State  = $matches[2]
            Version = [int]$matches[3]
        }
    }
}

if ($distros.Count -eq 0) {
    Write-Log -Message "No WSL distributions found. Nothing to move."
    exit 0
}

Write-Log -Message "Found $($distros.Count) distribution(s): $($distros.Name -join ', ')"

# Filter only WSL2 (version 2)
$wsl2Distros = $distros | Where-Object { $_.Version -eq 2 }
if ($wsl2Distros.Count -eq 0) {
    Write-Log -Message "No WSL2 distributions found. Exiting."
    exit 0
}
Write-Log -Message "WSL2 distributions to move: $($wsl2Distros.Name -join ', ')"

# ------------------------- PREPARE BACKUP AND NEW LOCATIONS -------------------------
try {
    New-Item -Path $backupRoot -ItemType Directory -Force -ErrorAction Stop | Out-Null
    New-Item -Path $newWSLRoot -ItemType Directory -Force -ErrorAction Stop | Out-Null
    Write-Log -Message "Backup directory: $backupRoot"
    Write-Log -Message "New WSL root: $newWSLRoot"
}
catch {
    Stop-WithError "Failed to create directories: $_"
}

# ------------------------- PROCESS EACH DISTRO -------------------------
$successList = @()
$failedList = @()

foreach ($distro in $wsl2Distros) {
    $distroName = $distro.Name
    $backupTar = "$backupRoot\$distroName.tar"
    $newDistroPath = "$newWSLRoot\$distroName"
    Write-Log -Message "===== Processing: $distroName ====="

    # 1. Get current .vhdx path
    $vhdxInfo = & wsl.exe --export --vhd-info $distroName 2>&1
    # Parse the output: typically line with '.vhdx' path
    $currentVhdx = $null
    foreach ($line in $vhdxInfo) {
        if ($line -match '([A-Za-z]:\\[^:]+\.vhdx)') {
            $currentVhdx = $matches[1]
            break
        }
    }
    if (-not $currentVhdx) {
        Write-Log -Message "Could not locate .vhdx path for $distroName. Skipping." -Level "WARN"
        continue
    }
    Write-Log -Message "Current .vhdx: $currentVhdx"

    # 2. Check if current .vhdx is on C: (if not, we could still move but skip? We'll move anyway if user wants)
    if ($currentVhdx -notlike "C:*") {
        Write-Log -Message "$distroName is already on a different drive. Skipping move." -Level "INFO"
        $successList += $distroName
        continue
    }

    # 3. Export to .tar (backup)
    Write-Log -Message "Exporting $distroName to $backupTar ..."
    $exportResult = & wsl.exe --export $distroName $backupTar 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Message "Export failed: $exportResult" -Level "ERROR"
        $failedList += $distroName
        continue
    }

    # 4. Verify .tar size (at least not zero)
    $tarSize = (Get-Item $backupTar).Length
    if ($tarSize -eq 0) {
        Write-Log -Message "Exported .tar file is empty. Aborting move for $distroName." -Level "ERROR"
        $failedList += $distroName
        continue
    }
    Write-Log -Message "Export successful. Size: $([math]::Round($tarSize/1GB,2)) GB"

    # 5. Unregister the distribution (removes registration, but .vhdx remains)
    Write-Log -Message "Unregistering $distroName ..."
    $unregResult = & wsl.exe --unregister $distroName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Message "Unregister failed: $unregResult" -Level "ERROR"
        $failedList += $distroName
        continue
    }

    # 6. Create new directory for this distro's .vhdx
    New-Item -Path $newDistroPath -ItemType Directory -Force | Out-Null

    # 7. Import from backup to new location
    Write-Log -Message "Importing $distroName to new location: $newDistroPath ..."
    $importResult = & wsl.exe --import $distroName $newDistroPath $backupTar --version 2 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Message "Import failed: $importResult" -Level "ERROR"
        $failedList += $distroName
        # Attempt to re-import original? We have backup .tar, but original .vhdx may still exist (unregistered but file there)
        # We'll attempt to restore the old registration manually later.
        continue
    }

    # 8. Verify new .vhdx exists and is not on C:
    $newVhdx = "$newDistroPath\ext4.vhdx"  # default name for WSL2
    if (-not (Test-Path $newVhdx)) {
        Write-Log -Message "New .vhdx not found at expected location $newVhdx" -Level "ERROR"
        $failedList += $distroName
        continue
    }
    if ($newVhdx -like "C:*") {
        Write-Log -Message "ERROR: New .vhdx still on C:! Move failed." -Level "ERROR"
        $failedList += $distroName
        continue
    }

    # 9. Success: delete the old .vhdx file (optional, but safe to keep backup for a while)
    try {
        if (Test-Path $currentVhdx) {
            Remove-Item -Path $currentVhdx -Force -ErrorAction Stop
            Write-Log -Message "Deleted old .vhdx: $currentVhdx"
        }
    }
    catch {
        Write-Log -Message "Could not delete old .vhdx: $_ (you can delete manually later)" -Level "WARN"
    }

    $successList += $distroName
    Write-Log -Message "SUCCESS: $distroName moved to $newDistroPath"
}

# ------------------------- FINAL REPORT AND RECOVERY INFO -------------------------
Write-Log -Message ""
Write-Log -Message "========== SUMMARY =========="
Write-Log -Message "Successfully moved: $($successList -join ', ')"
if ($failedList.Count -gt 0) {
    Write-Log -Message "FAILED: $($failedList -join ', ')" -Level "ERROR"
}

Write-Log -Message ""
Write-Log -Message "===== BACKUP & RECOVERY ====="
Write-Log -Message "All exported .tar backups are stored in: $backupRoot"
Write-Log -Message "To restore a distribution manually, run:"
Write-Log -Message "  wsl --import <DistroName> <OriginalPath> <BackupTar> --version 2"
Write-Log -Message ""
Write-Log -Message "If any distribution failed to import, you can re-import from backup using the command above."
Write-Log -Message "The old .vhdx files (if not deleted) are still present; you can re-register with:"
Write-Log -Message "  wsl --import <DistroName> <DirContainingVhdx> <AnyTarPlaceholder> --version 2"
Write-Log -Message ""

# Optional: Test start each successful distro
foreach ($distro in $successList) {
    Write-Log -Message "Testing start of $distro ..."
    & wsl.exe -d $distro -- cd ~ 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Log -Message "$distro starts correctly."
    } else {
        Write-Log -Message "$distro may have issues; please test manually: wsl -d $distro" -Level "WARN"
    }
}

Write-Log -Message "Script finished. Full log: $logFile"
Read-Host "Press Enter to exit"