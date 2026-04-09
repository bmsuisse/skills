# find_python.ps1 — resolves the Python 3 executable and exports it as $env:PYTHON.
# Dot-source this file to set $env:PYTHON in the current session:
#
#   . scripts/find_python.ps1
#   & $env:PYTHON some_script.py
#
# Or call it directly to print the resolved path:
#
#   powershell -File scripts/find_python.ps1   → prints resolved path

$candidates = @("python3", "python", "python3.12", "python3.11", "python3.10")

foreach ($candidate in $candidates) {
    $exe = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($exe) {
        $ver = & $candidate -c "import sys; print(sys.version_info.major)" 2>$null
        if ($ver -eq "3") {
            if ($MyInvocation.InvocationName -eq ".") {
                # Dot-sourced: export to current session
                $env:PYTHON = $candidate
                Write-Host "PYTHON=$candidate"
            } else {
                # Run directly: just print
                Write-Output $candidate
            }
            exit 0
        }
    }
}

Write-Error "No Python 3 interpreter found. Install Python 3 and retry."
exit 1
