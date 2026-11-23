$procs = Get-Process | Where-Object { $_.ProcessName -match 'Pylon' }
if (-not $procs) { Write-Output 'no pylon process'; exit }
foreach ($p in $procs) {
    Write-Output ('killing ' + $p.Id + ' ' + $p.ProcessName)
    try { Stop-Process -Id $p.Id -Force } catch { Write-Output ('failed: ' + $_.Exception.Message) }
}
Start-Sleep -Milliseconds 800
$after = Get-Process | Where-Object { $_.ProcessName -match 'Pylon' }
if ($after) { Write-Output 'still running' } else { Write-Output 'camera free' }
