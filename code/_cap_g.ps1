Set-Location $PSScriptRoot
cmd /c "python -u psf_capture.py --mask binary --n 32 --frames 8 --bin 4 --exposure-us 20 --z-mm 40 --d-mm 50 --seed 0 --out runs\g_bin > g_bin.log 2>&1"
Get-Content -Encoding Default g_bin.log | Select-Object -Last 4
cmd /c "python -u psf_capture.py --mask flat --n 1 --frames 8 --bin 4 --exposure-us 20 --out runs\g_flat > g_flat.log 2>&1"
Get-Content -Encoding Default g_flat.log | Select-Object -Last 3
