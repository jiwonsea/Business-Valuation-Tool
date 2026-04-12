# Register the weekly valuation pipeline as a Windows Scheduled Task.
# Run once from an elevated PowerShell prompt:
#   PowerShell -ExecutionPolicy Bypass -File scheduler\setup_task.ps1
#
# Schedule: Every Saturday at 09:00 KST (local time).
# Logs:      logs\weekly_YYYYMMDD.log  (written by weekly_run.py)

$TaskName  = "ValuationWeeklyRun"
$BatPath   = "F:\dev\Portfolio\business-valuation-tool\scheduler\run_weekly.bat"
$TriggerAt = "09:00AM"

# Remove existing task if present (idempotent re-registration)
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task '$TaskName'."
}

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At $TriggerAt

# StartWhenAvailable: run at next boot if PC was off at trigger time
# ExecutionTimeLimit: 2-hour cap to prevent hung processes
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Action      $action `
    -Trigger     $trigger `
    -Settings    $settings `
    -RunLevel    Highest `
    -Description "Weekly valuation pipeline: news discovery + AI analysis + Excel upload"

Write-Host ""
Write-Host "Task '$TaskName' registered. Next run: Saturday $TriggerAt KST."
Write-Host "To run immediately: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To check status:    Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "To remove:          Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
