Set-Location $PSScriptRoot
foreach ($e in 100, 1000, 10000) {
    $log = "probe_$e.log"
    cmd /c "python -u psf_capture.py --mask flat --n 1 --frames 4 --bin 4 --exposure-us $e --out runs\probe_$e > $log 2>&1"
    $line = Get-Content -Encoding Default $log | Select-String -Pattern 'mean=' | Select-Object -Last 1
    Write-Output ("exposure $e us -> " + $line)
}
